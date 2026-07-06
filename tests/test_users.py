"""User provisioning lifecycle: invite -> accept -> login, password reset,
and deactivation (Phase 1 of the IAM roadmap)."""
from datetime import datetime, timedelta

import data.database as dbmod
from auth import create_access_token, get_user_by_email
from conftest import _TEST_PASSWORD, auth_headers

NEW_PASSWORD = "BrandNewPass1234!"


def _invite_and_get_token(role="employee", email="invitee@test.local", name="Invitee"):
    """Creates an invited user directly against the DB (bypassing the
    email step) so tests can act on the raw token deterministically,
    the same way conftest creates fixture users directly."""
    user_id = dbmod.create_invited_user(name, email, role, "Finance", None)
    raw_token = dbmod.create_invite_token(user_id)
    return user_id, raw_token


def test_invite_requires_manager(client, employee_token):
    res = client.post(
        "/api/users/invite",
        json={"name": "X", "email": "blocked@test.local", "role": "employee", "department": "Finance"},
        headers=auth_headers(employee_token),
    )
    assert res.status_code == 403


def test_invite_creates_pending_user(client, manager_token):
    res = client.post(
        "/api/users/invite",
        json={"name": "New Hire", "email": "new-hire@test.local", "role": "employee", "department": "Sales"},
        headers=auth_headers(manager_token),
    )
    assert res.status_code == 201
    assert res.json()["status"] == "invited"


def test_invite_duplicate_email_rejected(client, manager_token):
    client.post(
        "/api/users/invite",
        json={"name": "Dup", "email": "dup@test.local", "role": "employee", "department": "Sales"},
        headers=auth_headers(manager_token),
    )
    res = client.post(
        "/api/users/invite",
        json={"name": "Dup Again", "email": "dup@test.local", "role": "employee", "department": "Sales"},
        headers=auth_headers(manager_token),
    )
    assert res.status_code == 409


def test_list_users_requires_manager(client, employee_token):
    res = client.get("/api/users", headers=auth_headers(employee_token))
    assert res.status_code == 403


def test_list_users_excludes_password_hash(client, manager_token):
    res = client.get("/api/users", headers=auth_headers(manager_token))
    assert res.status_code == 200
    users = res.json()
    assert len(users) > 0
    assert all("password_hash" not in u for u in users)


def test_accept_invite_invalid_token_rejected(client):
    res = client.post("/api/auth/accept-invite", json={"token": "not-a-real-token", "password": NEW_PASSWORD})
    assert res.status_code == 400


def test_full_invite_accept_login_flow(client):
    user_id, raw_token = _invite_and_get_token(email="full-flow@test.local")

    res = client.post("/api/auth/accept-invite", json={"token": raw_token, "password": NEW_PASSWORD})
    assert res.status_code == 200
    assert res.json()["status"] == "activated"

    login_res = client.post(
        "/api/auth/login",
        data={"username": "full-flow@test.local", "password": NEW_PASSWORD},
    )
    assert login_res.status_code == 200

    # A used invite token can't be replayed.
    replay_res = client.post("/api/auth/accept-invite", json={"token": raw_token, "password": "SomethingElse123!"})
    assert replay_res.status_code == 400


def test_expired_invite_token_rejected(client):
    user_id, raw_token = _invite_and_get_token(email="expired-invite@test.local")

    # Force the token's expiry into the past, the same way an integration
    # test would simulate time passing without actually sleeping 24h.
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    with dbmod._connection() as conn:
        conn.execute(
            "UPDATE invite_tokens SET expires_at = ? WHERE token_hash = ?",
            (past, dbmod._hash_token(raw_token)),
        )

    res = client.post("/api/auth/accept-invite", json={"token": raw_token, "password": NEW_PASSWORD})
    assert res.status_code == 400


def test_forgot_password_unknown_email_returns_generic_response(client):
    res = client.post("/api/auth/forgot-password", json={"email": "nobody-at-all@test.local"})
    assert res.status_code == 200
    assert res.json()["status"] == "if_account_exists_email_sent"


def test_reset_password_invalid_token_rejected(client):
    res = client.post(
        "/api/auth/reset-password", json={"token": "not-a-real-token-at-all", "password": NEW_PASSWORD}
    )
    assert res.status_code == 400


def test_reset_password_flow_invalidates_old_session(client):
    # Isolated account so this doesn't touch the shared employee/manager
    # fixtures. The "before" token is minted directly rather than via
    # /api/auth/login -- the login endpoint is rate-limited (10/minute)
    # and shared across the whole test session, so this test only spends
    # one of its login calls on the assertion that actually needs it.
    dbmod.create_user("Reset Test", "reset-test@test.local", _TEST_PASSWORD, "employee", "Finance")
    user = get_user_by_email("reset-test@test.local")
    old_token = create_access_token({"sub": user["email"], "tv": user["token_version"]})
    assert client.get("/api/auth/me", headers=auth_headers(old_token)).status_code == 200

    raw_reset_token = dbmod.create_password_reset_token("reset-test@test.local")
    assert raw_reset_token is not None

    reset_res = client.post(
        "/api/auth/reset-password", json={"token": raw_reset_token, "password": NEW_PASSWORD}
    )
    assert reset_res.status_code == 200

    # The token issued before the reset must no longer work...
    assert client.get("/api/auth/me", headers=auth_headers(old_token)).status_code == 401
    # ...but the new password logs in fine.
    new_login = client.post(
        "/api/auth/login",
        data={"username": "reset-test@test.local", "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200


def test_suspend_blocks_login_and_existing_session(client, manager_token):
    # Token minted directly (see comment in the reset-password test above)
    # so this test only spends one login call -- on the "suspended users
    # can't log in" assertion, which is the one that actually needs it.
    dbmod.create_user("Suspend Test", "suspend-test@test.local", _TEST_PASSWORD, "employee", "Finance")
    user = get_user_by_email("suspend-test@test.local")
    token = create_access_token({"sub": user["email"], "tv": user["token_version"]})
    user_id = client.get("/api/auth/me", headers=auth_headers(token)).json()["id"]

    suspend_res = client.patch(
        f"/api/users/{user_id}", json={"status": "suspended"}, headers=auth_headers(manager_token)
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["status"] == "suspended"

    # Existing session is rejected immediately, not just on next login attempt.
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 401

    relogin_res = client.post(
        "/api/auth/login",
        data={"username": "suspend-test@test.local", "password": _TEST_PASSWORD},
    )
    assert relogin_res.status_code == 401


def test_cannot_deactivate_self(client, manager_token):
    me = client.get("/api/auth/me", headers=auth_headers(manager_token)).json()
    res = client.patch(
        f"/api/users/{me['id']}", json={"status": "suspended"}, headers=auth_headers(manager_token)
    )
    assert res.status_code == 400


def test_count_active_managers_reflects_suspensions(client, manager_token):
    # A fresh, isolated manager -- the shared fixture manager is left
    # untouched throughout so no other test in the suite is affected.
    id_b = dbmod.create_user("Mgr B", "mgr-b@test.local", _TEST_PASSWORD, "manager", "Management")

    total_before = dbmod.count_active_managers()
    res = client.patch(
        f"/api/users/{id_b}", json={"status": "suspended"}, headers=auth_headers(manager_token)
    )
    assert res.status_code == 200
    total_after = dbmod.count_active_managers()
    assert total_after == total_before - 1
