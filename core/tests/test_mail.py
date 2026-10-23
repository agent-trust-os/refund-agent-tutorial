import json
import os
import urllib.request

import pytest

from refund_core.config import new_shop
from refund_core.mail import MemoryMailer, SmtpMailer
from refund_core.shop import Shop

MAILPIT_API = os.environ.get("MAILPIT_API")  # e.g. http://localhost:8025
SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
needs_mailpit = pytest.mark.skipif(not MAILPIT_API, reason="MAILPIT_API not set")


def api(path: str, method: str = "GET"):
    req = urllib.request.Request(MAILPIT_API + path, method=method)
    with urllib.request.urlopen(req) as r:
        text = r.read().decode()
    return json.loads(text) if text.startswith(("{", "[")) else text


def test_memory_mailer_records_messages():
    mailer = MemoryMailer()
    assert mailer.send("a@example.com", "hi", "body") == "M-0001"
    assert mailer.send("b@example.com", "yo", "text") == "M-0002"
    assert mailer.outbox == [
        {"message_id": "M-0001", "to": "a@example.com", "subject": "hi", "body": "body"},
        {"message_id": "M-0002", "to": "b@example.com", "subject": "yo", "body": "text"},
    ]


def test_shop_sends_through_its_mailer():
    mailer = MemoryMailer()
    shop = Shop(mailer=mailer)
    result = shop.send_email("alice@example.com", "Your refund", "We refunded $40.")
    assert result == {"ok": True, "message_id": "M-0001"}
    assert shop.outbox == mailer.outbox and shop.count("send_email") == 1


def test_default_shop_still_has_an_outbox():
    shop = Shop()
    shop.send_email("a@example.com", "s", "b")
    assert shop.outbox[0]["message_id"] == "M-0001"


def test_smtp_host_switches_the_shop_to_the_smtp_mailer(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert isinstance(new_shop().mailer, MemoryMailer)
    monkeypatch.setenv("SMTP_HOST", "mail.internal")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_FROM", "support@shop.test")
    mailer = new_shop().mailer
    assert isinstance(mailer, SmtpMailer)
    assert (mailer.host, mailer.port, mailer.sender) == ("mail.internal", 2525, "support@shop.test")


def test_an_unreachable_smtp_server_raises_instead_of_pretending_to_send():
    with pytest.raises(OSError):
        SmtpMailer("127.0.0.1", 1, timeout=2).send("a@example.com", "s", "b")


@needs_mailpit
def test_smtp_mailer_delivers_to_mailpit():
    api("/api/v1/messages", "DELETE")
    message_id = SmtpMailer(SMTP_HOST, SMTP_PORT).send("alice@example.com", "Your refund", "We refunded $40.")
    messages = api("/api/v1/messages")["messages"]
    assert len(messages) == 1
    assert messages[0]["To"][0]["Address"] == "alice@example.com"
    assert messages[0]["Subject"] == "Your refund"
    assert messages[0]["From"]["Address"] == "support@example.com"
    assert message_id.strip("<>") == messages[0]["MessageID"]
