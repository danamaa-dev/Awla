import hashlib
import json
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "awla.db")

VALID_STATUSES = (
    "pending_clarification", "pending_approval", "open",
    "in_progress", "overdue", "completed", "rejected",
)

# Governance state machine: which status transitions are allowed. Enforced
# by the API layer so a rejected/completed request can't be silently
# reopened or re-approved (see set_status / approve_request / reject_request
# in api/main.py).
ALLOWED_TRANSITIONS = {
    "pending_clarification": {"pending_clarification", "pending_approval"},
    "pending_approval": {"open", "rejected"},
    "open": {"in_progress", "overdue", "completed", "rejected"},
    "in_progress": {"completed", "overdue", "rejected"},
    "overdue": {"in_progress", "completed", "rejected"},
    "completed": set(),
    "rejected": set(),
}


def is_valid_transition(current_status: str, new_status: str) -> bool:
    if new_status not in VALID_STATUSES:
        return False
    if current_status == new_status:
        return True
    return new_status in ALLOWED_TRANSITIONS.get(current_status, set())


@contextmanager
def _connection():
    """Single place that owns connection lifecycle, WAL mode, and FK
    enforcement, so every caller gets try/finally cleanup and a consistent
    transaction (commit on success, rollback on error) for free."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema migrations ────────────────────────────────────────────────────────
# Versioned via SQLite's built-in PRAGMA user_version rather than a bespoke
# try/except ALTER TABLE loop, and rather than pulling in Alembic (which
# targets SQLAlchemy, not the raw sqlite3 access used throughout this
# project). Each migration is idempotent and ordered; applied migrations are
# never re-run.

_MIGRATIONS = []


def _migration(version: int, description: str):
    def decorator(fn):
        _MIGRATIONS.append((version, description, fn))
        return fn
    return decorator


@_migration(1, "baseline tables")
def _m1(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            department TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            department TEXT NOT NULL,
            report_type TEXT NOT NULL,
            format TEXT NOT NULL,
            deadline TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            priority_score REAL DEFAULT 0,
            recommendation TEXT DEFAULT 'MEDIUM',
            reasons TEXT DEFAULT '[]',
            repriority_log TEXT DEFAULT '[]',
            days_open INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            submitted_by INTEGER,
            submitted_by_name TEXT,
            submitted_by_department TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meeting_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


@_migration(2, "add indexes on requests(status, submitted_by, priority_score)")
def _m2(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_submitted_by ON requests(submitted_by)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_priority_score ON requests(priority_score DESC)")


@_migration(3, "rebuild requests table with FK(users) + CHECK(status)")
def _m3(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(requests)")}
    for col, ddl in [
        ("submitted_by", "ALTER TABLE requests ADD COLUMN submitted_by INTEGER"),
        ("submitted_by_name", "ALTER TABLE requests ADD COLUMN submitted_by_name TEXT"),
        ("submitted_by_department", "ALTER TABLE requests ADD COLUMN submitted_by_department TEXT"),
    ]:
        if col not in cols:
            conn.execute(ddl)

    conn.execute(f"""
        CREATE TABLE requests_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            department TEXT NOT NULL,
            report_type TEXT NOT NULL,
            format TEXT NOT NULL,
            deadline TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ({','.join(repr(s) for s in VALID_STATUSES)})),
            priority_score REAL DEFAULT 0,
            recommendation TEXT DEFAULT 'MEDIUM',
            reasons TEXT DEFAULT '[]',
            repriority_log TEXT DEFAULT '[]',
            days_open INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            submitted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            submitted_by_name TEXT,
            submitted_by_department TEXT
        )
    """)
    valid_list = ",".join(repr(s) for s in VALID_STATUSES)
    conn.execute(f"""
        INSERT INTO requests_new
        SELECT id, title, description, department, report_type, format, deadline,
               CASE WHEN status IN ({valid_list}) THEN status ELSE 'open' END,
               priority_score, recommendation, reasons, repriority_log, days_open,
               created_at, submitted_by, submitted_by_name, submitted_by_department
        FROM requests
    """)
    conn.execute("DROP TABLE requests")
    conn.execute("ALTER TABLE requests_new RENAME TO requests")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_submitted_by ON requests(submitted_by)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_priority_score ON requests(priority_score DESC)")


@_migration(4, "rebuild users table with CHECK(role)")
def _m4(conn):
    conn.execute("""
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee' CHECK (role IN ('employee', 'manager')),
            department TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO users_new
        SELECT id, name, email, password_hash,
               CASE WHEN role IN ('employee', 'manager') THEN role ELSE 'employee' END,
               department, created_at
        FROM users
    """)
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")


@_migration(5, "add user lifecycle columns (status, token_version, invited_by) and invite/reset token tables")
def _m5(conn):
    # password_hash becomes nullable: an invited user has a row (so their
    # email/role/department are already assigned) but no password until
    # they accept the invite and set one themselves.
    conn.execute("""
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            role TEXT NOT NULL DEFAULT 'employee' CHECK (role IN ('employee', 'manager')),
            department TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('invited', 'active', 'suspended')),
            token_version INTEGER NOT NULL DEFAULT 0,
            invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO users_new (id, name, email, password_hash, role, department, status, token_version, invited_by, created_at)
        SELECT id, name, email, password_hash, role, department, 'active', 0, NULL, created_at
        FROM users
    """)
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")

    # Tokens are stored hashed (sha256 of a 32-byte random value is plenty --
    # unlike a password, there's no low-entropy guessing risk to defend
    # against with a slow hash; hashing here is purely so a DB dump alone
    # doesn't hand out live invite/reset links).
    conn.execute("""
        CREATE TABLE invite_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_tokens_hash ON invite_tokens(token_hash)")

    conn.execute("""
        CREATE TABLE password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash ON password_reset_tokens(token_hash)")


def _run_migrations(conn):
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, description, fn in sorted(_MIGRATIONS, key=lambda m: m[0]):
        if version <= current:
            continue
        logger.info("applying migration %d: %s", version, description)
        fn(conn)
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()


def init_db():
    """No demo/seed accounts are created here. A previous version of this
    app seeded hardcoded accounts with guessable passwords (e.g.
    "manager123") on every startup, and shipped them in the frontend's
    login screen too -- both removed deliberately. Use
    `python scripts/create_user.py` to create the first real account."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        # FK checks are disabled while migrations may rebuild referenced
        # tables (users), then re-enabled for normal operation.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA journal_mode = WAL")
        _run_migrations(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    finally:
        conn.close()


def create_user(name: str, email: str, password: str, role: str, department: str) -> int:
    """Used by scripts/create_user.py (first-admin bootstrap) and by the
    test suite to create fixtures directly with a password already set.
    Day-to-day account creation goes through create_invited_user() instead,
    so a new user picks their own password rather than an admin knowing it."""
    import bcrypt as _bcrypt
    hashed = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    with _connection() as conn:
        cur = conn.execute("""
            INSERT INTO users (name, email, password_hash, role, department)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, hashed, role, department))
        return cur.lastrowid


# ── User lifecycle: invitations, activation, password reset ───────────────────

INVITE_TOKEN_TTL_HOURS = 24
RESET_TOKEN_TTL_HOURS = 1


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_raw_token() -> str:
    return secrets.token_urlsafe(32)


def create_invited_user(name: str, email: str, role: str, department: str, invited_by: int) -> int:
    """Creates a user row with no password and status='invited'. The user
    isn't a real account yet -- create_invite_token() below must be called
    and the resulting link sent to them before they can activate it."""
    with _connection() as conn:
        cur = conn.execute("""
            INSERT INTO users (name, email, password_hash, role, department, status, invited_by)
            VALUES (?, ?, NULL, ?, ?, 'invited', ?)
        """, (name, email, role, department, invited_by))
        return cur.lastrowid


def create_invite_token(user_id: int) -> str:
    """Returns the raw token (only ever available here, at creation time --
    only its hash is persisted) so the caller can email it."""
    raw = _new_raw_token()
    expires_at = (datetime.now() + timedelta(hours=INVITE_TOKEN_TTL_HOURS)).isoformat()
    with _connection() as conn:
        conn.execute("""
            INSERT INTO invite_tokens (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, _hash_token(raw), expires_at))
    return raw


def accept_invite(raw_token: str, password: str) -> bool:
    """Sets the invited user's password and activates the account. Returns
    False (no exception) for any invalid/expired/reused token so the caller
    can return a uniform 400 without distinguishing why."""
    import bcrypt as _bcrypt
    token_hash = _hash_token(raw_token)
    with _connection() as conn:
        row = conn.execute("""
            SELECT id, user_id, expires_at, used_at FROM invite_tokens WHERE token_hash = ?
        """, (token_hash,)).fetchone()
        if not row or row["used_at"] or datetime.fromisoformat(row["expires_at"]) < datetime.now():
            return False
        hashed = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
        conn.execute("""
            UPDATE users SET password_hash = ?, status = 'active', token_version = token_version + 1
            WHERE id = ?
        """, (hashed, row["user_id"]))
        conn.execute("UPDATE invite_tokens SET used_at = ? WHERE id = ?", (datetime.now().isoformat(), row["id"]))
        return True


def create_password_reset_token(email: str) -> Optional[str]:
    """Returns the raw token, or None if there's no active account with
    that email -- callers must respond identically either way so an
    unauthenticated caller can't use this to enumerate accounts."""
    with _connection() as conn:
        user = conn.execute("SELECT id, status FROM users WHERE email = ?", (email,)).fetchone()
        if not user or user["status"] != "active":
            return None
        raw = _new_raw_token()
        expires_at = (datetime.now() + timedelta(hours=RESET_TOKEN_TTL_HOURS)).isoformat()
        conn.execute("""
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        """, (user["id"], _hash_token(raw), expires_at))
        return raw


def reset_password_with_token(raw_token: str, password: str) -> bool:
    """Bumps token_version so any JWT issued before the reset is rejected
    on its next use, even though it hasn't hit its 8h expiry yet."""
    import bcrypt as _bcrypt
    token_hash = _hash_token(raw_token)
    with _connection() as conn:
        row = conn.execute("""
            SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token_hash = ?
        """, (token_hash,)).fetchone()
        if not row or row["used_at"] or datetime.fromisoformat(row["expires_at"]) < datetime.now():
            return False
        hashed = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
        conn.execute("""
            UPDATE users SET password_hash = ?, token_version = token_version + 1
            WHERE id = ?
        """, (hashed, row["user_id"]))
        conn.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
            (datetime.now().isoformat(), row["id"]),
        )
        return True


def list_users() -> list:
    with _connection() as conn:
        rows = conn.execute("""
            SELECT id, name, email, role, department, status, created_at
            FROM users ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_user_by_id(user_id: int):
    with _connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user(
    user_id: int,
    role: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
) -> bool:
    """Any status change also bumps token_version, so a session in flight
    is invalidated on its next request rather than remaining valid until
    its 8h JWT expiry -- get_current_user checks status directly too, so
    this is defense-in-depth for status specifically, and the only
    invalidation mechanism for a plain password reset."""
    fields, params = [], []
    if role is not None:
        fields.append("role = ?")
        params.append(role)
    if department is not None:
        fields.append("department = ?")
        params.append(department)
    if status is not None:
        fields.append("status = ?")
        params.append(status)
        fields.append("token_version = token_version + 1")
    if not fields:
        return False
    params.append(user_id)
    with _connection() as conn:
        cur = conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
        return cur.rowcount > 0


def count_active_managers(exclude_id: Optional[int] = None) -> int:
    with _connection() as conn:
        if exclude_id is not None:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM users WHERE role = 'manager' AND status = 'active' AND id != ?",
                (exclude_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM users WHERE role = 'manager' AND status = 'active'"
            ).fetchone()
        return row["c"]


# ── Requests ─────────────────────────────────────────────────────────────────

def get_all_requests():
    with _connection() as conn:
        rows = conn.execute("""
            SELECT * FROM requests
            WHERE status NOT IN ('pending_clarification')
            ORDER BY priority_score DESC
        """).fetchall()
        return [_parse_row(row) for row in rows]


def get_requests_by_user(user_id: int):
    with _connection() as conn:
        rows = conn.execute("""
            SELECT * FROM requests
            WHERE submitted_by = ? AND status NOT IN ('pending_clarification')
            ORDER BY priority_score DESC
        """, (user_id,)).fetchall()
        return [_parse_row(row) for row in rows]


def get_request_by_id(req_id: int):
    with _connection() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (req_id,)).fetchone()
        return _parse_row(row) if row else None


def _parse_row(row):
    r = dict(row)
    r["reasons"] = json.loads(r.get("reasons") or "[]")
    r["repriority_log"] = json.loads(r.get("repriority_log") or "[]")
    return r


def insert_request(req: dict) -> int:
    with _connection() as conn:
        cur = conn.execute("""
            INSERT INTO requests
                (title, description, department, report_type, format, deadline,
                 status, priority_score, recommendation, reasons, days_open,
                 submitted_by, submitted_by_name, submitted_by_department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (
            req["title"], req["description"], req["department"],
            req.get("report_type", ""), req.get("format", ""), req["deadline"],
            req.get("status", "open"),
            req.get("priority_score", 0), req.get("recommendation", "MEDIUM"),
            json.dumps(req.get("reasons", [])),
            req.get("submitted_by"), req.get("submitted_by_name"), req.get("submitted_by_department"),
        ))
        return cur.lastrowid


def update_request_after_clarification(req_id: int, description: str, status: str,
                                        priority_score: float, recommendation: str, reasons: list):
    with _connection() as conn:
        conn.execute("""
            UPDATE requests
            SET description=?, status=?, priority_score=?, recommendation=?, reasons=?
            WHERE id=?
        """, (description, status, priority_score, recommendation, json.dumps(reasons), req_id))


def update_request_status(req_id: int, new_status: str):
    with _connection() as conn:
        conn.execute("UPDATE requests SET status=? WHERE id=?", (new_status, req_id))


def update_request_priority(req_id: int, new_score: float, reason: str):
    """Atomic single-statement update: appends to repriority_log via SQLite's
    JSON1 functions instead of a read-modify-write round trip, so concurrent
    calls can no longer lose an update (previously a real race — see audit
    finding L1)."""
    rec = "Critical" if new_score >= 9 else "High" if new_score >= 7 else "Medium" if new_score >= 5 else "Low"
    entry = json.dumps({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "new_score": new_score,
        "reason": reason,
    })
    with _connection() as conn:
        conn.execute("""
            UPDATE requests
            SET priority_score = ?,
                recommendation = ?,
                repriority_log = json_insert(COALESCE(repriority_log, '[]'), '$[#]', json(?))
            WHERE id = ?
        """, (new_score, rec, entry, req_id))


def save_meeting_report(report: dict):
    with _connection() as conn:
        conn.execute("INSERT INTO meeting_reports (report) VALUES (?)", (json.dumps(report),))


def get_latest_meeting_report():
    with _connection() as conn:
        row = conn.execute(
            "SELECT report, created_at FROM meeting_reports ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            return json.loads(row["report"]), row["created_at"]
        return None, None
