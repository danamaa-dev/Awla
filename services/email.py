"""Transactional email for account invites and password resets -- the only
outbound email Awla sends. Built on stdlib smtplib rather than adding a new
dependency. If SMTP_HOST isn't configured (local dev, CI, tests), messages
are logged instead of sent, so the app never crashes or blocks on a missing
mail server; the invite/reset token is already persisted in the database
either way, so an admin can resend or the flow can be tested via the log."""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "Awla <no-reply@awla.local>")


def _send(to: str, subject: str, body: str) -> None:
    if not SMTP_HOST:
        logger.info("Email (SMTP_HOST not set, logging only) to=%s subject=%r\n%s", to, subject, body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except OSError:
        # The invite/reset token is already committed to the database, so a
        # transient SMTP failure shouldn't fail the whole request -- the
        # admin can see the account is still "invited" and resend.
        logger.exception("Failed to send email to=%s subject=%r", to, subject)


def send_invite_email(to: str, name: str, token: str) -> None:
    link = f"{FRONTEND_URL}/accept-invite?token={token}"
    _send(
        to,
        "You've been invited to Awla",
        f"Hi {name},\n\n"
        "You've been invited to join Awla. Set your password to activate your account:\n\n"
        f"{link}\n\n"
        "This link expires in 24 hours.",
    )


def send_reset_email(to: str, name: str, token: str) -> None:
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    _send(
        to,
        "Reset your Awla password",
        f"Hi {name},\n\n"
        "A password reset was requested for your Awla account. If this was you:\n\n"
        f"{link}\n\n"
        "This link expires in 1 hour. If you didn't request this, you can ignore this email.",
    )
