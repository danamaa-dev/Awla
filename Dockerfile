# Python 3.12, not the 3.14 this project was developed against locally --
# chromadb's native vector-index extension was found (during this audit
# remediation) to hard-crash under 3.14 in the dev sandbox. 3.12 is within
# chromadb's officially supported range, so this also sidesteps that
# issue for real deployments rather than just working around it.
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runtime data (SQLite databases, Chroma persistence) lives outside the
# image so it survives container recreation -- see docker-compose.yml.
RUN mkdir -p /app/data /app/chroma_data

ENV CHROMA_PERSIST_DIR=/app/chroma_data
EXPOSE 8000

# urllib (stdlib) instead of httpx -- httpx isn't a runtime dependency of
# the app itself, only of the test suite's TestClient (requirements-dev.txt).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
