"""LangGraph orchestration for the request-intake pipeline.

Three of the four agents in this system participate in a genuine
multi-step, conditionally-branching pipeline that runs as part of a single
user action (submitting or re-clarifying a request):

    clarification --[gate]--> rag --> priority

LangGraph earns its place here specifically because that gate is a real
conditional branch (an incomplete request skips RAG/priority entirely and
returns early), and because keeping this as an explicit graph rather than
a chain of if/else calls makes it straightforward to extend later -- e.g.
a retry loop after clarification, or a human-in-the-loop checkpoint --
without restructuring the whole flow (audit finding M8).

The other two agents are deliberately NOT part of this graph:
  - execution_agent runs when a user clicks "Execute"/"Download" on an
    already-approved request -- a separate action with no clarification
    or priority step involved.
  - report_agent runs when a manager generates a meeting summary across
    many requests at once -- also unrelated to the single-request intake
    flow above.
Folding either into this graph would add indirection with no orchestration
benefit. Agent responsibilities are otherwise non-overlapping -- intake
completeness, scoring, SQL/chart generation, and meeting summarization --
so there is no merge/removal candidate among them.
"""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.clarification_agent import run_clarification_agent
from agents.priority_agent import run_priority_agent
from rag.chromadb_client import query_chromadb


class RequestState(TypedDict):
    request: dict
    chroma_client: Any
    clarification_result: dict
    rag_context: str
    priority_result: dict


def clarification_node(state: RequestState) -> RequestState:
    state["clarification_result"] = run_clarification_agent(state["request"])
    return state


def rag_node(state: RequestState) -> RequestState:
    description = state["request"].get("description", "")
    state["rag_context"] = query_chromadb(description, client=state.get("chroma_client"))
    return state


def priority_node(state: RequestState) -> RequestState:
    state["priority_result"] = run_priority_agent(
        request=state["request"],
        rag_context=state["rag_context"],
    )
    return state


def should_clarify(state: RequestState) -> str:
    status = state["clarification_result"].get("status", "incomplete")
    return "proceed" if status == "complete" else "needs_clarification"


def build_workflow():
    workflow = StateGraph(RequestState)

    workflow.add_node("clarification", clarification_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("priority", priority_node)

    workflow.set_entry_point("clarification")

    workflow.add_conditional_edges(
        "clarification",
        should_clarify,
        {
            "proceed": "rag",
            "needs_clarification": END,
        },
    )

    workflow.add_edge("rag", "priority")
    workflow.add_edge("priority", END)

    return workflow.compile()


# Compiled once at import time. Previously build_workflow() ran (and
# recompiled the graph) on every single call to run_workflow -- i.e. on
# every request submission and every clarification -- which was pure
# avoidable overhead on every request (audit finding M7).
_COMPILED_WORKFLOW = build_workflow()


def run_workflow(request: dict, chroma_client=None) -> dict:
    """Runs the intake pipeline for one request. `chroma_client` should be
    the process-wide Chroma client built at API startup (see
    api/main.py) -- previously this was expected to arrive stuffed inside
    request["_chroma_client"], a key nothing ever actually set, so RAG
    context was always the empty fallback in production (audit finding
    C9). It is now an explicit parameter threaded through the graph
    state instead."""
    initial_state = RequestState(
        request=request,
        chroma_client=chroma_client,
        clarification_result={},
        rag_context="",
        priority_result={},
    )
    return _COMPILED_WORKFLOW.invoke(initial_state)


if __name__ == "__main__":
    print("=== Test 1: Vague Request ===")
    vague_request = {
        "title": "Sales Report",
        "description": "I need a sales report",
        "department": "Finance",
        "deadline": "2026-06-25",
        "days_open": 3,
        "format": "Excel",
        "report_type": "Excel"
    }
    result1 = run_workflow(vague_request)
    print(f"Clarification Status: {result1['clarification_result']['status']}")
    print(f"Questions: {result1['clarification_result']['questions']}")
    print()

    print("=== Test 2: Complete Request ===")
    complete_request = {
        "title": "Monthly Sales Report",
        "description": "Monthly sales report for Q2 2026, grouped by region, from sales system, delivered as Excel",
        "department": "Finance",
        "deadline": "2026-06-25",
        "days_open": 3,
        "format": "Excel",
        "report_type": "Excel"
    }
    result2 = run_workflow(complete_request)
    print(f"Clarification Status: {result2['clarification_result']['status']}")
    print(f"Priority Score: {result2['priority_result'].get('score', 'N/A')}")
    print(f"Recommendation: {result2['priority_result'].get('recommendation', 'N/A')}")
    print()
    print("Workflow works successfully")
