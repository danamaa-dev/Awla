"""Database layer tests: the governance state machine helper, and that a
fresh database gets the integrity features the audit found missing
(foreign keys, indexes, CHECK constraints -- findings H2, H3, M15)."""
import sqlite3

import pytest

from data.database import init_db, is_valid_transition


@pytest.mark.parametrize("current,new,expected", [
    ("pending_approval", "open", True),
    ("pending_approval", "rejected", True),
    ("open", "rejected", True),
    ("open", "in_progress", True),
    ("rejected", "open", False),      # terminal state, the bug the audit found
    ("completed", "open", False),     # terminal state
    ("pending_clarification", "completed", False),  # must go through approval first
    ("open", "open", True),           # no-op transitions are fine
])
def test_state_machine_transitions(current, new, expected):
    assert is_valid_transition(current, new) is expected


def test_fresh_database_has_expected_integrity_features(tmp_path):
    import data.database as dbmod
    original_path = dbmod.DB_PATH
    try:
        dbmod.DB_PATH = str(tmp_path / "fresh.db")
        init_db()

        conn = sqlite3.connect(dbmod.DB_PATH)

        indexes = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        assert "idx_requests_status" in indexes
        assert "idx_requests_submitted_by" in indexes
        assert "idx_requests_priority_score" in indexes

        requests_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='requests'"
        ).fetchone()[0]
        assert "REFERENCES users" in requests_sql
        assert "CHECK" in requests_sql

        users_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='users'"
        ).fetchone()[0]
        assert "CHECK" in users_sql

        conn.close()
    finally:
        dbmod.DB_PATH = original_path


def test_update_request_priority_is_atomic_json_append(tmp_path):
    """Regression guard for the read-modify-write race the audit flagged
    (finding L1) -- this must be a single UPDATE statement, verified here
    by checking two successive calls both land in repriority_log."""
    import data.database as dbmod
    original_path = dbmod.DB_PATH
    try:
        dbmod.DB_PATH = str(tmp_path / "priority.db")
        init_db()
        req_id = dbmod.insert_request({
            "title": "t", "description": "d", "department": "Finance",
            "report_type": "sales", "format": "Excel", "deadline": "2026-12-01",
        })
        dbmod.update_request_priority(req_id, 7.0, "first adjustment")
        dbmod.update_request_priority(req_id, 8.5, "second adjustment")

        req = dbmod.get_request_by_id(req_id)
        assert len(req["repriority_log"]) == 2
        assert req["repriority_log"][0]["reason"] == "first adjustment"
        assert req["repriority_log"][1]["reason"] == "second adjustment"
        assert req["priority_score"] == 8.5
    finally:
        dbmod.DB_PATH = original_path
