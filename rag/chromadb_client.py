import logging

from rag.embedding import embed_texts

logger = logging.getLogger(__name__)

# Results markedly farther from the query than the closest match are
# dropped rather than unconditionally included just because they made the
# top-K cut (audit finding H8). This is a relative cutoff (vs. the best
# match in the same query) rather than a fixed distance, so it works the
# same way regardless of which embedding backend produced the vectors.
_RELATIVE_DISTANCE_CUTOFF = 1.8


def _filtered_documents(documents: list[str], distances: list[float]) -> list[str]:
    if not documents:
        return []
    best = distances[0] if distances else None
    seen = set()
    kept = []
    for doc, dist in zip(documents, distances):
        if doc in seen:
            continue
        if best is not None and best > 0 and dist is not None and dist > best * _RELATIVE_DISTANCE_CUTOFF:
            continue
        seen.add(doc)
        kept.append(doc)
    return kept


def query_chromadb(request_description: str, n_results: int = 3, client=None) -> str:
    if client is None:
        return "No RAG context available. ChromaDB client not provided."

    try:
        policies_col = client.get_collection(name="department_policies")
        history_col = client.get_collection(name="request_history")
        types_col = client.get_collection(name="request_types")

        p_count = policies_col.count()
        h_count = history_col.count()
        t_count = types_col.count()

        if p_count == 0 or h_count == 0 or t_count == 0:
            return "No RAG context available. Collections are empty."

        query_embedding = embed_texts([request_description])

        policies_results = policies_col.query(
            query_embeddings=query_embedding,
            n_results=min(n_results, p_count),
            include=["documents", "distances"],
        )
        history_results = history_col.query(
            query_embeddings=query_embedding,
            n_results=min(2, h_count),
            include=["documents", "distances"],
        )
        types_results = types_col.query(
            query_embeddings=query_embedding,
            n_results=min(2, t_count),
            include=["documents", "distances"],
        )
    except Exception:
        logger.exception("ChromaDB query failed")
        return "No RAG context available. Retrieval failed."

    policies = _filtered_documents(policies_results["documents"][0], policies_results["distances"][0])
    history = _filtered_documents(history_results["documents"][0], history_results["distances"][0])
    types = _filtered_documents(types_results["documents"][0], types_results["distances"][0])

    if not (policies or history or types):
        return "No RAG context available. No sufficiently relevant matches found."

    context = """
=== RELEVANT POLICIES ===
{policies}

=== SIMILAR PAST REQUESTS ===
{history}

=== REQUEST TYPE REQUIREMENTS ===
{types}
""".format(
        policies="\n".join(policies) or "(none sufficiently relevant)",
        history="\n".join(history) or "(none sufficiently relevant)",
        types="\n".join(types) or "(none sufficiently relevant)",
    )

    return context
