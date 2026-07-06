import hashlib
import logging
import math
import os

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    _openai_available = False

_EMBEDDING_MODEL = "text-embedding-3-small"
_HASH_DIM = 256


def _hash_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic hashing-trick fallback, used only when no OpenAI API
    key is configured. This has no semantic understanding at all --
    synonyms, paraphrase, and word order are all invisible to it, and it
    only "works" when a query happens to reuse the literal vocabulary of
    the indexed documents. It exists purely so RAG degrades gracefully
    instead of crashing when there's no API key, mirroring the same
    try-LLM-then-fallback pattern every other agent in this codebase uses.
    It must never be the primary embedding path when a real model is
    available (this was previously the *only* embedding implementation --
    see audit finding C8)."""
    result = []
    for text in texts:
        vec = [0.0] * _HASH_DIM
        for word in text.lower().split():
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            vec[h % _HASH_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        result.append([x / norm for x in vec])
    return result


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Real semantic embeddings via OpenAI when a key is configured,
    falling back to the hashing scheme above otherwise. Whichever path is
    used, it must stay the same for both indexing (chromadb_setup/setup.py)
    and querying (rag/chromadb_client.py) within a single running process,
    since the two embedding schemes produce vectors of different
    dimensionality (1536 vs 256) that are not comparable in the same
    Chroma collection."""
    api_key = os.getenv("OPENAI_API_KEY")
    if _openai_available and api_key:
        try:
            client = OpenAI(api_key=api_key)
            response = client.embeddings.create(model=_EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in response.data]
        except Exception:
            logger.exception("OpenAI embeddings call failed; falling back to hashing-based embedding")

    return _hash_embed(texts)
