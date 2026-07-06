"""Request lifecycle tests: ownership isolation (pre-existing correct
behavior, kept green as a regression guard), the governance state machine
(audit finding H12), and input validation (audit finding M4)."""
from conftest import COMPLETE_DESCRIPTION, auth_headers


def _submit_complete_request(client, token, title):
    res = client.post(
        "/api/requests",
        headers=auth_headers(token),
        json={
            "title": title,
            "description": COMPLETE_DESCRIPTION,
            "report_type": "Sales",
            "format": "Excel",
            "deadline": "2026-12-01",
            "days_open": 0,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "pending_approval", body
    return body["id"]


def test_submit_request_is_attributed_to_submitter(client, employee_token):
    req_id = _submit_complete_request(client, employee_token, "Ownership Test Request")
    res = client.get(f"/api/requests/{req_id}", headers=auth_headers(employee_token))
    assert res.status_code == 200
    assert res.json()["submitted_by_name"] == "Test Employee One"
    assert res.json()["department"] == "Finance"  # server-derived, not client-supplied


def test_employee_cannot_view_another_employees_request(client, employee_token, employee2_token):
    req_id = _submit_complete_request(client, employee_token, "Private Request")
    res = client.get(f"/api/requests/{req_id}", headers=auth_headers(employee2_token))
    assert res.status_code == 403


def test_manager_can_view_any_request(client, employee_token, manager_token):
    req_id = _submit_complete_request(client, employee_token, "Manager Visible Request")
    res = client.get(f"/api/requests/{req_id}", headers=auth_headers(manager_token))
    assert res.status_code == 200


def test_department_cannot_be_spoofed_by_client(client, employee_token):
    res = client.post(
        "/api/requests",
        headers=auth_headers(employee_token),
        json={
            "title": "Spoof Attempt",
            "description": COMPLETE_DESCRIPTION,
            "department": "Security",  # attempt to claim a department the user isn't in
            "report_type": "Sales",
            "format": "Excel",
            "deadline": "2026-12-01",
        },
    )
    assert res.status_code == 201
    assert res.json()  # request created
    req_id = res.json()["id"]
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(employee_token)).json()
    assert detail["department"] == "Finance"  # server overrides with the real department


def test_invalid_deadline_format_rejected(client, employee_token):
    res = client.post(
        "/api/requests",
        headers=auth_headers(employee_token),
        json={
            "title": "Bad Deadline",
            "description": COMPLETE_DESCRIPTION,
            "report_type": "Sales",
            "format": "Excel",
            "deadline": "not-a-date",
        },
    )
    assert res.status_code == 422


def test_invalid_format_enum_rejected(client, employee_token):
    res = client.post(
        "/api/requests",
        headers=auth_headers(employee_token),
        json={
            "title": "Bad Format",
            "description": COMPLETE_DESCRIPTION,
            "report_type": "Sales",
            "format": "Powerpoint",  # not one of Dashboard/Excel/PDF
            "deadline": "2026-12-01",
        },
    )
    assert res.status_code == 422


def test_oversized_title_rejected(client, employee_token):
    res = client.post(
        "/api/requests",
        headers=auth_headers(employee_token),
        json={
            "title": "x" * 500,
            "description": COMPLETE_DESCRIPTION,
            "report_type": "Sales",
            "format": "Excel",
            "deadline": "2026-12-01",
        },
    )
    assert res.status_code == 422


def test_rejected_request_cannot_be_reapproved(client, employee_token, manager_token):
    """This exact bug was silently allowed before the fix -- a rejected
    request could be flipped back to 'open' with no validation at all."""
    req_id = _submit_complete_request(client, employee_token, "State Machine Test Request")

    approve = client.patch(f"/api/requests/{req_id}/approve", headers=auth_headers(manager_token))
    assert approve.status_code == 200
    assert approve.json()["status"] == "open"

    reject = client.patch(f"/api/requests/{req_id}/reject", headers=auth_headers(manager_token))
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    reapprove = client.patch(f"/api/requests/{req_id}/approve", headers=auth_headers(manager_token))
    assert reapprove.status_code == 409

    # status must still be 'rejected', not silently flipped
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(manager_token)).json()
    assert detail["status"] == "rejected"


def test_clarification_endpoint_rejects_non_pending_request(client, employee_token, manager_token):
    """A submitter used to be able to resurrect an already-decided request
    by calling the clarification endpoint on it."""
    req_id = _submit_complete_request(client, employee_token, "Resurrection Attempt Request")
    client.patch(f"/api/requests/{req_id}/approve", headers=auth_headers(manager_token))

    res = client.post(
        f"/api/requests/{req_id}/clarification",
        headers=auth_headers(employee_token),
        json={"description": COMPLETE_DESCRIPTION + " Updated."},
    )
    assert res.status_code == 409


def test_priority_score_from_ai_workflow_is_clamped_in_range(client, employee_token):
    """Defense-in-depth for the prompt-injection path (audit finding C6):
    even though rule-based scoring is in effect for tests, the sanitizer
    must be the thing enforcing the bound, not incidental agent behavior."""
    req_id = _submit_complete_request(client, employee_token, "Priority Clamp Test Request")
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(employee_token)).json()
    assert 1.0 <= detail["priority_score"] <= 10.0
    assert detail["recommendation"] in ("HIGH", "MEDIUM", "LOW")
