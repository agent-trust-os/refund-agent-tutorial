"""The tools the agent can call: the same eight as the FastAPI agent, as LangChain tools.

Each tool is a ``@tool`` function with the model's own arguments plus ``config`` (hidden from the model),
through which it gets the database, the ticket and the request (``context.py``). ``@logged`` writes every
call to the action log before the tool runs. This is where AgentTrust guards each tool (``governance.py``).
"""
from __future__ import annotations

from .customers import lookup_customer
from .email import send_email
from .governance import govern
from .orders import lookup_order, purge_orders
from .refunds import issue_refund
from .tickets import create_ticket, read_ticket, update_ticket

ALL_TOOLS = [govern(t) for t in (read_ticket, lookup_order, lookup_customer, issue_refund, send_email,
                                 create_ticket, update_ticket, purge_orders)]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
