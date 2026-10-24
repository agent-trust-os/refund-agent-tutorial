"""Deliver an email over SMTP. In Docker the server is Mailpit, which catches every email and delivers none,
so nothing can reach a real person. With SMTP_HOST unset, nothing is delivered and the email is only
kept in the database (see the send_email tool)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..core.config import get_settings


def deliver(to: str, subject: str, body: str) -> bool:
    """Send the email if a mail server is configured. Returns whether it was sent; raises if the server is down."""
    settings = get_settings()
    if not settings.smtp_host:
        return False
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.smtp_from, to, subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)
    return True
