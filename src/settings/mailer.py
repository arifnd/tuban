"""Outbound email using the SMTP settings configured on the Settings page."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from src.exceptions import BadRequestError
from src.settings import service as settings_service

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15


def _build_message(*, config: dict[str, Any], to: str, subject: str, body: str) -> EmailMessage:
    sender = str(config.get("smtp_from_email") or config.get("smtp_username") or "")
    from_name = str(config.get("smtp_from_name") or "")
    message = EmailMessage()
    if sender:
        message["From"] = formataddr((from_name, sender)) if from_name else sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


def _send(config: dict[str, Any], message: EmailMessage, password: str) -> None:
    host = str(config.get("smtp_host") or "")
    port = int(config.get("smtp_port") or 587)
    username = str(config.get("smtp_username") or "")
    use_ssl = bool(config.get("smtp_use_ssl"))
    use_tls = bool(config.get("smtp_use_tls"))
    client = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS) if use_ssl else smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
    try:
        if use_tls and not use_ssl:
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)
    finally:
        client.quit()


async def send_email(*, to: str, subject: str, body: str) -> None:
    """Send a plain-text email through the configured SMTP server.

    Raises ``BadRequestError`` with a user-facing message when email is disabled,
    unconfigured, or the SMTP server rejects the message.
    """
    config = settings_service.all()
    if not config.get("smtp_enabled"):
        raise BadRequestError(detail="Email sending is disabled in settings")
    if not config.get("smtp_host"):
        raise BadRequestError(detail="The SMTP host is not configured")
    if not to:
        raise BadRequestError(detail="No recipient address was provided")
    message = _build_message(config=config, to=to, subject=subject, body=body)
    password = settings_service.get_secret("smtp_password")
    try:
        await asyncio.to_thread(_send, config, message, password)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("SMTP send to %s failed: %s", to, exc)
        raise BadRequestError(detail="Could not send email through the configured SMTP server") from exc
