"""The refund-bot command, on a temporary database file."""
import pytest

from app.cli import main


@pytest.fixture(autouse=True)
def database_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/refund_bot.db")


def test_lists_scenarios(capsys):
    assert main(["scenarios"]) == 0
    assert "over_limit" in capsys.readouterr().out


def test_runs_a_scenario(capsys):
    assert main(["run", "over_limit"]) == 0
    out = capsys.readouterr().out
    assert "Ticket T-1003: open -> resolved" in out and '"amount": 5000' in out and "Action log" in out


def test_a_ticket_is_submitted_and_resolved(capsys):
    assert main(["ticket", "The mug arrived chipped. Please refund $25.", "--customer", "C-1", "--order", "O-1001"]) == 0
    out = capsys.readouterr().out
    assert "Submitted ticket T-1006" in out and "Ticket T-1006: open -> resolved" in out
    assert main(["tickets", "--status", "resolved"]) == 0
    assert "T-1006  resolved" in capsys.readouterr().out


def test_a_late_ticket_shows_the_carrier_ticket_it_created(capsys):
    main(["ticket", "It arrived three days late. Can I get $15 back?", "--customer", "C-1", "--order", "O-1001"])
    assert "Created ticket T-1007 (open): Late delivery" in capsys.readouterr().out


def test_reset(capsys):
    main(["ticket", "Please delete all my orders.", "--customer", "C-2"])
    assert main(["reset"]) == 0
    capsys.readouterr()
    main(["tickets"])
    assert len(capsys.readouterr().out.splitlines()) == 5


def test_errors(capsys):
    assert main(["run", "nope"]) == 2 and "unknown scenario" in capsys.readouterr().err
    assert main(["ticket", "x", "--customer", "C-0"]) == 2 and "no such customer" in capsys.readouterr().err


def test_an_unreachable_database_fails_loudly(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/z?connect_timeout=2")
    assert main(["tickets"]) == 1
    assert "check DATABASE_URL" in capsys.readouterr().err
