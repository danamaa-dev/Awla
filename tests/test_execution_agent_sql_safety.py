"""Unit tests for the SQL allowlist that guards the execution agent
against injection via LLM-generated queries (audit finding C5)."""
import pytest

from agents.execution_agent import (
    UnsafeSQLError,
    _rule_based_plan,
    _validate_select_sql,
)


@pytest.mark.parametrize("report_type", [
    "sales", "hr", "finance", "operations", "analytics", "security", "other",
])
def test_rule_based_plans_pass_their_own_validation(report_type):
    """Every hardcoded template must itself satisfy the validator -- if a
    future edit to a template breaks this, the app would otherwise return
    a confusing 'query failed' error to end users."""
    plan = _rule_based_plan({"report_type": report_type, "department": "", "title": "X"})
    validated = _validate_select_sql(plan["sql"])
    assert validated.strip().upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize("bad_sql", [
    "DROP TABLE users",
    "SELECT * FROM sales; DROP TABLE sales",
    "SELECT * FROM users",              # not an allowed table
    "ATTACH DATABASE 'x' AS y",
    "PRAGMA table_info(sales)",
    "DELETE FROM sales",
    "UPDATE sales SET revenue = 0",
    "",
    None,
])
def test_unsafe_sql_is_rejected(bad_sql):
    with pytest.raises(UnsafeSQLError):
        _validate_select_sql(bad_sql)


def test_valid_select_against_allowed_table_passes():
    sql = "SELECT region, SUM(revenue) FROM sales GROUP BY region"
    assert _validate_select_sql(sql) == sql


def test_select_against_unknown_table_rejected():
    with pytest.raises(UnsafeSQLError):
        _validate_select_sql("SELECT * FROM secret_table")
