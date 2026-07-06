import logging
import os
import sys

# Ensure project root is importable when auth is imported standalone
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from data.database import _connection

logger = logging.getLogger(__name__)

# Load .env independently of import order — this module must not depend on
# some other module (e.g. api/main.py) having already called load_dotenv().
load_dotenv(os.path.join(_root, ".env"))

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. Refusing to start with an "
        "insecure default (this used to fall back to a hardcoded string, which "
        "let anyone with source access forge admin tokens). Generate one with:\n"
        '    python -c "import secrets; print(secrets.token_hex(32))"\n'
        "and set it in your .env file."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

# The React app authenticates via an httpOnly cookie (not readable by JS,
# so an XSS bug can no longer just read the token out of localStorage --
# audit finding H14). API-style clients (tests, curl, scripts) can keep
# sending a normal Authorization: Bearer header instead -- both are
# accepted by get_current_user below.
COOKIE_NAME = "awla_token"

# auto_error=False so a request with no Authorization header falls through
# to the cookie check instead of get_current_user rejecting it immediately.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(email: str):
    with _connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_current_user(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
) -> dict:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = header_token or request.cookies.get(COOKIE_NAME)
    if not token:
        raise exc
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise exc
    except JWTError:
        raise exc

    user = get_user_by_email(email)
    if not user:
        raise exc
    # Re-fetched fresh on every request (not cached in the token), so a
    # role or department change takes effect immediately. status and
    # token_version specifically need to be checked against the token's
    # own "tv" claim: a suspension or password reset must invalidate a
    # session immediately rather than waiting out the 8h token expiry.
    if user["status"] != "active":
        raise exc
    if payload.get("tv") != user["token_version"]:
        raise exc
    return user


def require_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return current_user
