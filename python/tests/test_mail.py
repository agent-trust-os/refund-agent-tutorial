"""Delivering email. The Mailpit test runs only where MAILPIT_API is set (the compose test service)."""
import json
import os
import urllib.request

import pytest

from app.services.mail import deliver

MAILPIT_API = os.environ.get("MAILPIT_API")            # http://mailpit:8025 in compose
MAILPIT_SMTP = os.environ.get("MAILPIT_SMTP_HOST", "localhost")


def test_without_a_mail_server_nothing_is_delivered():
    assert deliver("a@example.com", "s", "b") is False


def test_a_mail_server_that_is_down_raises(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1")
    with pytest.raises(OSError):
        deliver("a@example.com", "s", "b")


@pytest.mark.skipif(not MAILPIT_API, reason="MAILPIT_API not set")
def test_delivers_to_mailpit(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", MAILPIT_SMTP)
    urllib.request.urlopen(urllib.request.Request(MAILPIT_API + "/api/v1/messages", method="DELETE"))
    assert deliver("alice@example.com", "Your refund", "We refunded $40.") is True
    with urllib.request.urlopen(MAILPIT_API + "/api/v1/messages") as r:
        messages = json.load(r)["messages"]
    assert [(m["To"][0]["Address"], m["Subject"], m["From"]["Address"]) for m in messages] == [
        ("alice@example.com", "Your refund", "support@example.com")]
