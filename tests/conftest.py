"""Shared pytest fixtures.

Tests run against a real FastAPI app instance, but with two deliberate
substitutions so the suite is fast, deterministic, and doesn't depend on
network access or the fragile native chromadb extension documented in
graph/workflow.py and chromadb_setup/setup.py:

  1. OPENAI_API_KEY is forced empty before anything is imported, so every
     agent takes its deterministic rule-based path instead of calling out
     to a real LLM.
  2. chromadb_setup.setup.setup_chromadb is replaced with a no-op that
     returns None (RAG unavailable) *before* api/main.py is ever imported,
     so tests never wait on -- or depend on the outcome of -- the
     subprocess-isolated indexing step.

Both substitutions happen once per test session, against an isolated
temporary SQLite database so tests never touch the real data/awla.db.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Must happen before any project module is imported.
os.environ["SECRET_KEY"] = "test-only-secret-do-not-use-in-production"
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
os.environ["OPENAI_API_KEY"] = ""  # force every agent onto its rule-based path

import pytest
from fastapi.testclient import TestClient

# There is no demo-account seeding in the app anymore (a previous version
# hardcoded guessable passwords like "manager123" -- removed deliberately).
# The test suite creates its own throwaway accounts directly in the
# isolated temp database created by the `client` fixture below.
_TEST_PASSWORD = "TestPass1234!"


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    import data.database as dbmod
    dbmod.DB_PATH = str(tmp_path_factory.mktemp("db") / "test_awla.db")

    import chromadb_setup.setup as chroma_setup_mod
    chroma_setup_mod.setup_chromadb = lambda timeout=90: None

    import main  # api/main.py
    dbmod.create_user("Test Employee One", "employee1@test.local", _TEST_PASSWORD, "employee", "Finance")
    dbmod.create_user("Test Employee Two", "employee2@test.local", _TEST_PASSWORD, "employee", "HR")
    dbmod.create_user("Test Manager", "manager@test.local", _TEST_PASSWORD, "manager", "Management")

    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="session")
def employee_token(client):
    res = client.post(
        "/api/auth/login",
        data={"username": "employee1@test.local", "password": _TEST_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="session")
def employee2_token(client):
    res = client.post(
        "/api/auth/login",
        data={"username": "employee2@test.local", "password": _TEST_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="session")
def manager_token(client):
    res = client.post(
        "/api/auth/login",
        data={"username": "manager@test.local", "password": _TEST_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# A description crafted to satisfy _rule_based_clarification's keyword
# checks (time period, metric, source, min length) so clarification
# completes deterministically without needing a real LLM call.
COMPLETE_DESCRIPTION = (
    "Monthly sales report for Q2 2026 grouped by region, sourced from the "
    "Salesforce CRM system, delivered as an Excel file."
)
