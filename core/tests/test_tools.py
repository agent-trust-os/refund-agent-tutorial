import pytest

from refund_core.models.base import tool_spec
from refund_core.shop import Shop
from refund_core.tools import make_tools

NAMES = ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "send_email", "update_ticket",
         "purge_orders"]


def test_every_tool_has_a_spec():
    tools = make_tools(Shop())
    assert list(tools) == NAMES and len(NAMES) == 7
    specs = [tool_spec(fn) for fn in tools.values()]
    assert [s.name for s in specs] == NAMES
    assert all(s.description for s in specs)


def test_issue_refund_spec():
    spec = tool_spec(make_tools(Shop())["issue_refund"])
    assert spec.parameters["type"] == "object"
    assert spec.parameters["required"] == ["order_id", "amount"]
    props = spec.parameters["properties"]
    assert props["amount"]["type"] == "number"
    assert props["order_id"]["type"] == "string"
    assert props["currency"]["default"] == "USD"
    assert "user" not in props and "input" not in props


def test_update_ticket_spec_and_call():
    shop = Shop()
    tools = make_tools(shop)
    spec = tool_spec(tools["update_ticket"])
    assert spec.parameters["required"] == ["ticket_id", "status"]
    assert spec.parameters["properties"]["note"]["default"] == ""
    assert tools["update_ticket"](ticket_id="T-1001", status="resolved", note="done", user="bot", input="x")["ok"]
    assert shop.tickets["T-1001"]["status"] == "resolved"


def test_purge_orders_has_empty_schema():
    spec = tool_spec(make_tools(Shop())["purge_orders"])
    assert spec.parameters == {"type": "object", "properties": {}, "required": []}


def test_no_spec_exposes_hidden_arguments():
    for fn in make_tools(Shop()).values():
        props = tool_spec(fn).parameters["properties"]
        assert "user" not in props and "input" not in props


def test_tools_call_the_shop_and_accept_hidden_kwargs():
    shop = Shop()
    tools = make_tools(shop)
    result = tools["issue_refund"](order_id="O-1001", amount=40, reason="late", user="bot", input="ticket text")
    assert result["ok"] and shop.count("issue_refund") == 1
    assert tools["lookup_order"]("O-1001")["order"]["total"] == 120.0


def test_unsupported_type_hint_is_rejected():
    def bad(x: list) -> dict:
        """Bad."""
        return {}

    with pytest.raises(TypeError):
        tool_spec(bad)
