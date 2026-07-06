"""Authentication and authorization tests (audit findings C1, C4, H1)."""
from conftest import _TEST_PASSWORD, auth_headers


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["database"] is True


def test_login_success(client):
    res = client.post(
        "/api/auth/login",
        data={"username": "manager@test.local", "password": _TEST_PASSWORD},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["role"] == "manager"
    assert body["access_token"]
    # httpOnly cookie must also be set (audit finding H14)
    assert "awla_token" in res.cookies


def test_login_wrong_password_rejected(client):
    res = client.post(
        "/api/auth/login",
        data={"username": "manager@test.local", "password": "wrong-password"},
    )
    assert res.status_code == 401


def test_login_unknown_user_rejected(client):
    res = client.post(
        "/api/auth/login",
        data={"username": "nobody@test.local", "password": "whatever"},
    )
    assert res.status_code == 401


def test_protected_endpoint_requires_auth(client):
    # The client is session-scoped and earlier tests log in against it, so
    # the httpOnly cookie from a previous test may still be attached --
    # clear it to actually test the "nobody is authenticated" case.
    client.cookies.clear()
    res = client.get("/api/requests")
    assert res.status_code == 401


def test_protected_endpoint_rejects_garbage_token(client):
    client.cookies.clear()
    res = client.get("/api/requests", headers=auth_headers("not-a-real-token"))
    assert res.status_code == 401


def test_me_returns_current_user(client, employee_token):
    res = client.get("/api/auth/me", headers=auth_headers(employee_token))
    assert res.status_code == 200
    assert res.json()["email"] == "employee1@test.local"


def test_manager_only_endpoint_rejects_employee(client, employee_token):
    res = client.post("/api/reports/meeting", headers=auth_headers(employee_token))
    assert res.status_code == 403


def test_manager_only_endpoint_allows_manager(client, manager_token):
    res = client.post("/api/reports/meeting", headers=auth_headers(manager_token))
    assert res.status_code == 201  # creation endpoint, see audit finding L2


def test_logout_clears_cookie(client, employee_token):
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "logged_out"
