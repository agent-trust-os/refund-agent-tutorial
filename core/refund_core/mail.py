"""How the shop sends email. ``MemoryMailer`` is the default (no services); ``SmtpMailer`` sends over
SMTP, which in the compose stack is Mailpit: it accepts every message and delivers none, so no
email can reach a real person."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any, Protocol


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> str:
        """Send one message and return its id."""


class MemoryMailer:
    def __init__(self) -> None:
        self.outbox: list[dict[str, Any]] = []

    def send(self, to: str, subject: str, body: str) -> str:
        message_id = f"M-{len(self.outbox) + 1:04d}"
        self.outbox.append({"message_id": message_id, "to": to, "subject": subject, "body": body})
        return message_id


class SmtpMailer:
    def __init__(self, host: str, port: int = 1025, sender: str = "support@example.com",
                 timeout: float = 10) -> None:
        self.host, self.port, self.sender, self.timeout = host, port, sender, timeout

    def send(self, to: str, subject: str, body: str) -> str:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.sender, to, subject
        message["Message-ID"] = make_msgid(domain="refund-bot.local")
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            smtp.send_message(message)
        return message["Message-ID"]
