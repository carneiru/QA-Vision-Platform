"""Sends the email-verification link.

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


class EmailSender:
    @staticmethod
    def send_verification_email(to_email: str, verification_link: str) -> None:
        body = (
            f"Click the link below to complete your registration:\n\n{verification_link}\n\n"
            "This link expires in 24 hours."
        )

        if not settings.SMTP_HOST:
            logger.info(
                "Verification email for %s (SMTP not configured, logging instead): %s",
                to_email, verification_link,
            )
            return

        message = EmailMessage()
        message["Subject"] = "Verify your email"
        message["From"] = settings.EMAILS_FROM_EMAIL or "no-reply@example.com"
        message["To"] = to_email
        message.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
