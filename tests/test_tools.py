import pytest

from refund_bot.models.base import tool_spec
from refund_bot.shop import Shop
from refund_bot.tools import make_tools

NAMES = ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "send_email", "purge_orders"]


def test_every_tool_has_a_spec():
    tools = make_tools(Shop(), run_id="r1")
    assert list(tools) == NAMES
    specs = [tool_spec(fn) for fn in tools.values()]
    assert [s.name for s in specs] == NAMES
    assert all(s.description for s in specs)


def test_issue_refund_spec():
    spec = tool_spec(make_tools(Shop(), run_id="r1")["issue_refund"])
    assert spec.parameters["type"] == "object"
    assert spec.parameters["required"] == ["order_id", "amount"]
    props = spec.parameters["properties"]
    assert props["amount"]["type"] == "number"
    assert props["order_id"]["type"] == "string"
    assert props["currency"]["default"] == "USD"
    assert "user" not in props and "input" not in props


def test_purge_orders_has_empty_schema():
    spec = tool_spec(make_tools(Shop(), run_id="r1")["purge_orders"])
    assert spec.parameters == {"type": "object", "properties": {}, "required": []}


def test_no_spec_exposes_hidden_arguments():
    for fn in make_tools(Shop(), run_id="r1").values():
        props = tool_spec(fn).parameters["properties"]
        assert "user" not in props and "input" not in props


def test_tools_call_the_shop_and_accept_hidden_kwargs():
    shop = Shop()
    tools = make_tools(shop, run_id="r1")
    result = tools["issue_refund"](order_id="O-1001", amount=40, reason="late", user="bot", input="ticket text")
    assert result["ok"] and shop.count("issue_refund") == 1
    assert tools["lookup_order"]("O-1001")["order"]["total"] == 120.0


def test_unsupported_type_hint_is_rejected():
    def bad(x: list) -> dict:
        """Bad."""
        return {}

    with pytest.raises(TypeError):
        tool_spec(bad)
