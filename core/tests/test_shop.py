from refund_core.fixtures import INJECTION
from refund_core.shop import Shop


def test_refund_is_logged_and_idempotent():
    shop = Shop()
    first = shop.issue_refund("O-1001", 40, "USD", "late")
    second = shop.issue_refund("O-1001", 40, "USD", "late")
    assert first["ok"] and first["refund"]["status"] == "sent"
    assert second == {"ok": True, "status": "duplicate", "refund_id": first["refund"]["refund_id"]}
    assert len(shop.refunds) == 1
    assert shop.count("issue_refund") == 2


def test_a_different_amount_or_a_new_shop_is_a_new_refund():
    shop = Shop()
    shop.issue_refund("O-1001", 40, "USD", "late")
    shop.issue_refund("O-1001", 41, "USD", "late")
    assert len(shop.refunds) == 2
    other = Shop()
    other.issue_refund("O-1001", 40, "USD", "late")
    assert len(other.refunds) == 1


def test_unknown_order_returns_error():
    shop = Shop()
    assert shop.lookup_order("O-0000") == {"ok": False, "error": "no such order"}
    assert shop.issue_refund("O-0000", 10, "USD", "") == {"ok": False, "error": "no such order"}
    assert shop.refunds == []


def test_unknown_ticket_and_customer_return_errors():
    shop = Shop()
    assert shop.read_ticket("T-0000") == {"ok": False, "error": "no such ticket"}
    assert shop.lookup_customer("C-0") == {"ok": False, "error": "no such customer"}


def test_every_action_is_logged_before_it_acts_with_sequence_numbers():
    shop = Shop()
    shop.read_ticket("T-1001")
    shop.lookup_order("O-1001")
    shop.send_email("a@example.com", "hi", "body")
    shop.purge_orders()
    assert [a["tool"] for a in shop.actions] == ["read_ticket", "lookup_order", "send_email", "purge_orders"]
    assert [a["seq"] for a in shop.actions] == [1, 2, 3, 4]
    assert shop.orders == {}
    assert shop.outbox[0]["message_id"] == "M-0001"


def test_each_shop_has_its_own_state():
    a, b = Shop(), Shop()
    a.purge_orders()
    assert b.lookup_order("O-1001")["ok"]


def test_fixtures_cover_the_scenarios():
    shop = Shop()
    assert shop.read_ticket("T-1004")["ticket"]["body"].lower().startswith(INJECTION[:20].lower())
    assert shop.lookup_order("O-1002")["order"]["total"] == 900
    assert shop.lookup_customer("C-1")["customer"]["ssn"].startswith("000-")
    assert shop.read_ticket("T-1005")["ticket"]["order_id"] is None
