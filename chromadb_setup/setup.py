import logging
import multiprocessing as mp
import os

import chromadb

from rag.embedding import embed_texts

logger = logging.getLogger(__name__)

# Curated organizational policy knowledge. These are short, discrete rules
# rather than long-form documents, so there is nothing to meaningfully
# chunk here -- each entry is already a single retrievable unit (audit
# finding H7).
policies_docs = [
    "Security and compliance reports have the highest priority. Must be completed within 24 hours.",
    "Operational reports SLA is 3 business days from submission date.",
    "Analytics and insights reports SLA is 5 business days.",
    "Ad-hoc reports SLA is 7 business days.",
    "If a request is overdue by more than 7 days, escalate priority automatically to score 9+.",
    "Requests affecting more than 2 departments are considered high priority.",
    "Finance department requests during end-of-quarter period are automatically escalated.",
    "Any request with a regulatory or audit tag must be treated as security-level priority.",
]

# Used only as a fallback when the requests database has no completed or
# rejected history yet (e.g. a brand-new deployment). Once real history
# exists, _live_history_docs() replaces these with actual data instead of
# leaving "similar past requests" permanently frozen at day-one examples
# (audit finding H7).
_seed_history_docs = [
    "Past request: Sales dashboard for Finance dept, Score 8.5, completed in 2 days, no blockers.",
    "Past request: Security audit report, Score 9.8, escalated due to compliance deadline.",
    "Past request: HR headcount report, Score 6.0, completed in 4 days, delayed due to missing data source.",
    "Past request: Marketing campaign analytics, Score 5.5, completed in 6 days.",
    "Past request: Operations daily report, Score 7.2, overdue 3 days due to system downtime.",
]

types_docs = [
    "Sales reports require: time period, grouping by region or product, data source, delivery format.",
    "HR reports require: department filter, data sensitivity level, manager approval before processing.",
    "Finance reports require: fiscal period, currency, consolidation level, delivery format.",
    "Operations reports require: process name, KPIs needed, frequency, data source.",
    "Security reports require: incident type, affected systems, date range, classification level.",
    "Dashboard requests require: KPIs to display, data refresh rate, user access level, data source.",
]


def _live_history_docs(limit: int = 50) -> list[str]:
    """Builds the 'similar past requests' knowledge from real completed/
    rejected requests instead of permanently-static examples."""
    try:
        from data.database import get_all_requests
        reqs = [r for r in get_all_requests() if r["status"] in ("completed", "rejected")]
    except Exception:
        logger.exception("Could not load request history from the database; using seed examples")
        return _seed_history_docs

    if not reqs:
        return _seed_history_docs

    return [
        f"Past request: {r['title']} ({r['department']}), report type {r['report_type']}, "
        f"priority score {r['priority_score']}, status {r['status']}, "
        f"open for {r['days_open']} day(s)."
        for r in reqs[-limit:]
    ]


def _index_collections(persist_dir: str) -> None:
    """The real indexing work: builds/refreshes the three Chroma
    collections. This runs inside an isolated subprocess (see
    setup_chromadb) because chromadb's native vector-index extension has
    been observed, in this project's test environment, to hard-crash
    (a genuine OS-level access violation -- not a catchable Python
    exception) on certain Python builds. Isolating it in its own process
    means that crash can never take down the API server -- at worst,
    indexing for that run is skipped and RAG context stays unavailable,
    which query_chromadb() already reports gracefully rather than erroring."""
    client = chromadb.PersistentClient(path=persist_dir)

    policies_col = client.get_or_create_collection(name="department_policies")
    history_col = client.get_or_create_collection(name="request_history")
    types_col = client.get_or_create_collection(name="request_types")

    if policies_col.count() == 0:
        policies_col.add(
            documents=policies_docs,
            embeddings=embed_texts(policies_docs),
            ids=[f"policy_{i}" for i in range(len(policies_docs))],
        )

    if types_col.count() == 0:
        types_col.add(
            documents=types_docs,
            embeddings=embed_texts(types_docs),
            ids=[f"type_{i}" for i in range(len(types_docs))],
        )

    live_docs = _live_history_docs()
    if history_col.count():
        history_col.delete(ids=history_col.get()["ids"])
    history_col.add(
        documents=live_docs,
        embeddings=embed_texts(live_docs),
        ids=[f"history_{i}" for i in range(len(live_docs))],
    )

    logger.info(
        "ChromaDB indexed (persist_dir=%s): policies=%d, history=%d, types=%d",
        persist_dir, policies_col.count(), history_col.count(), types_col.count(),
    )


def _index_worker(persist_dir: str, conn) -> None:
    """Entry point for the isolated indexing subprocess. Must stay at
    module scope (not nested) so it can be pickled by multiprocessing's
    spawn start method."""
    try:
        _index_collections(persist_dir)
        conn.send(("ok", None))
    except Exception as e:
        conn.send(("error", str(e)))
    finally:
        conn.close()


def _run_indexing_isolated(persist_dir: str, timeout: int) -> None:
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe()
    proc = ctx.Process(target=_index_worker, args=(persist_dir, child_conn))
    proc.start()
    child_conn.close()
    try:
        if parent_conn.poll(timeout):
            status, error = parent_conn.recv()
            proc.join(timeout=5)
            if status == "error":
                logger.error("ChromaDB indexing failed: %s", error)
                return False
            return True
        logger.error("ChromaDB indexing timed out after %ss; terminating", timeout)
        proc.terminate()
        proc.join(timeout=5)
        return False
    except (EOFError, BrokenPipeError, OSError):
        proc.join(timeout=5)
        logger.error(
            "ChromaDB indexing subprocess crashed (exit code %s). This usually means "
            "the chromadb native extension is incompatible with the current Python "
            "build -- RAG context will be unavailable until this is resolved (try a "
            "Python version chromadb officially supports, e.g. 3.11-3.12).",
            proc.exitcode,
        )
        return False


def setup_chromadb(timeout: int = 90):
    """Indexes (or re-syncs) the Chroma collections in an isolated
    subprocess, then returns a client in this process for querying at
    request time -- or None if indexing failed.

    A crashed .add() call was observed to leave the on-disk store in a
    state that then crashes *any* future process trying to even open it,
    not just add to it -- so on failure the persist directory is wiped
    and this returns None (RAG unavailable) rather than risking a second
    crash by opening a possibly-poisoned store in the caller's own
    process. query_chromadb() already reports client=None as RAG being
    unavailable rather than erroring (audit finding C9's persistence half)."""
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

    try:
        ok = _run_indexing_isolated(persist_dir, timeout)
    except Exception:
        logger.exception("Could not run ChromaDB indexing subprocess")
        ok = False

    if not ok:
        if os.path.isdir(persist_dir):
            import shutil
            shutil.rmtree(persist_dir, ignore_errors=True)
        logger.warning("ChromaDB unavailable this run -- RAG context will be reported as unavailable")
        return None

    return chromadb.PersistentClient(path=persist_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_chromadb()
