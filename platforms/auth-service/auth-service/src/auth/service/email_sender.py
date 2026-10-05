"""Sends the email-verification and password-reset links.

SMTP_HOST and friends already existed in config.py, unread. Unlike Google SSO (which fails
closed with 503 when unconfigured -- verifying without an audience would be a worse hole
than refusing), this cannot fail closed: every development and test environment lacking a
real SMTP server would be unable to register at all, which is unacceptable for a control
this central. When SMTP_HOST is empty (the default), the link is logged instead of sent.
"""
import logging
import smtplib
from email.message import EmailMessage

from src.auth.config import settings

logger = logging.getLogger(__name__)


def _deliver(to_email: str, subject: str, body: str, kind: str, link: str) -> None:
    if not settings.SMTP_HOST:
        # WARNING, not INFO: the root logger defaults to WARNING, so an INFO
        # line never reaches the container log — and this link is the only
        # way to finish the flow on a deployment without SMTP
        logger.warning("%s for %s (SMTP not configured, logging instead): %s", kind, to_email, link)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAILS_FROM_EMAIL or "no-reply@example.com"
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)


class EmailSender:
    @staticmethod
    def send_verification_email(to_email: str, verification_link: str) -> None:
        body = (
            f"Click the link below to complete your registration:\n\n{verification_link}\n\n"
            "This link expires in 24 hours."
        )
        _deliver(to_email, "Verify your email", body, "Verification email", verification_link)

    @staticmethod
    def send_password_reset_email(to_email: str, reset_link: str, expire_minutes: int) -> None:
        body = (
            f"Someone asked to reset the password of your QA Vision account.\n\n{reset_link}\n\n"
            f"The link works once and expires in {expire_minutes} minutes. If you did not ask "
            "for this, ignore this email: your password stays as it is."
        )
        _deliver(to_email, "Reset your password", body, "Password reset email", reset_link)
