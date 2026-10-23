"""A small HTTP server so the Refund Bot runs as a service (``docker compose up``).

Standard library only. Two ways to use it:

* ``POST /run/<scenario>``: play a scripted scenario on a fresh shop, in one call.
* The ticket workflow: ``POST /runs`` makes a workspace, ``POST /runs/<id>/tickets`` submits a ticket,
  ``POST /runs/<id>/tickets/<ticket>/resolve`` lets the agent resolve it, ``GET /runs/<id>`` shows the
  state. With Postgres the workspace lives in the database, so it survives between requests; in memory
  the server keeps it open.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from refund_core.config import new_shop, open_shop
from refund_core.models.mock import MockModel
from refund_core.models.rules import RuleModel
from refund_core.scenarios import BY_ID, SCENARIOS, Scenario
from refund_core.shop import Shop

from .agent import RunResult, run

ENDPOINTS = [
    "GET /health", "GET /scenarios", "POST /run/{scenario}",
    "POST /runs", "GET /runs/{run}", "POST /runs/{run}/tickets",
    "GET /runs/{run}/tickets/{ticket}", "POST /runs/{run}/tickets/{ticket}/resolve",
]

_MEMORY_RUNS: dict[str, Shop] = {}   # only used when DATABASE_URL is not set
RUN = re.compile(r"^/runs/([\w-]+)$")
TICKETS = re.compile(r"^/runs/([\w-]+)/tickets$")
TICKET = re.compile(r"^/runs/([\w-]+)/tickets/([\w-]+)$")
RESOLVE = re.compile(r"^/runs/([\w-]+)/tickets/([\w-]+)/resolve$")


def _postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def _find(run_id: str) -> Shop | None:
    return open_shop(run_id) if _postgres() else _MEMORY_RUNS.get(run_id)


def _release(shop: Shop) -> None:
    if _postgres():
        shop.close()


def _result_body(shop: Shop, result: RunResult) -> dict[str, Any]:
    return {"run_id": shop.run_id, "answer": result.answer, "transcript": [asdict(m) for m in result.transcript],
            "actions": result.actions, "ticket": result.ticket, "created_tickets": result.created_tickets}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: Any) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _with_run(self, run_id: str, handler) -> None:
        shop = _find(run_id)
        if shop is None:
            self._send(404, {"error": f"unknown run {run_id!r}"})
            return
        try:
            handler(shop)
        finally:
            _release(shop)

    # ---------------------------------------------------------------- GET
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        elif self.path == "/scenarios":
            self._send(200, [{"id": s.id, "module": s.module, "ticket_id": s.ticket_id} for s in SCENARIOS])
        elif self.path == "/":
            self._send(200, {"app": "refund-bot", "endpoints": ENDPOINTS})
        elif m := RUN.match(self.path):
            self._with_run(m[1], lambda shop: self._send(200, {
                "run_id": shop.run_id, "tickets": shop.tickets, "refunds": shop.refunds, "actions": shop.actions}))
        elif m := TICKET.match(self.path):
            self._with_run(m[1], lambda shop: self._get_ticket(shop, m[2]))
        else:
            self._send(404, {"error": "not found"})

    def _get_ticket(self, shop: Shop, ticket_id: str) -> None:
        ticket = shop.tickets.get(ticket_id)
        if ticket is None:
            self._send(404, {"error": f"no such ticket {ticket_id!r}"})
        else:
            self._send(200, {"run_id": shop.run_id, "ticket": ticket})

    # --------------------------------------------------------------- POST
    def do_POST(self) -> None:
        if self.path.startswith("/run/"):
            self._play_scenario(self.path[len("/run/"):])
        elif self.path == "/runs":
            self._new_run()
        elif m := TICKETS.match(self.path):
            self._with_run(m[1], self._submit_ticket)
        elif m := RESOLVE.match(self.path):
            self._with_run(m[1], lambda shop: self._resolve_ticket(shop, m[2]))
        else:
            self._send(404, {"error": "not found"})

    def _open_new_shop(self) -> Shop | None:
        try:
            return new_shop()
        except Exception as exc:
            self._send(503, {"error": f"could not open the shop (check DATABASE_URL): {exc}"})
            return None

    def _play_scenario(self, scenario_id: str) -> None:
        scenario = BY_ID.get(scenario_id)
        if scenario is None:
            self._send(404, {"error": f"unknown scenario {scenario_id!r}"})
            return
        shop = self._open_new_shop()
        if shop is None:
            return
        with shop:
            result = run(scenario, MockModel(scenario), shop)
        self._send(200, {"scenario": scenario.id, **_result_body(shop, result)})

    def _new_run(self) -> None:
        shop = self._open_new_shop()
        if shop is None:
            return
        if not _postgres():
            _MEMORY_RUNS[shop.run_id] = shop
        try:
            self._send(201, {
                "run_id": shop.run_id,
                "tickets": [{"ticket_id": t["ticket_id"], "customer_id": t["customer_id"], "status": t["status"]}
                            for t in shop.tickets.values()],
                "orders": [{"order_id": o["order_id"], "customer_id": o["customer_id"], "total": o["total"]}
                           for o in shop.orders.values()]})
        finally:
            _release(shop)

    def _submit_ticket(self, shop: Shop) -> None:
        data = self._json_body()
        if data is None:
            self._send(400, {"error": "the body must be a JSON object"})
        elif not data.get("body") or not data.get("customer_id"):
            self._send(400, {"error": "body is required" if data.get("customer_id") else "customer_id is required"})
        else:
            result = shop.submit_ticket(data["customer_id"], data["body"], data.get("order_id") or "")
            if result["ok"]:
                self._send(201, {"run_id": shop.run_id, "ticket": result["ticket"]})
            else:
                self._send(400, {"error": result["error"]})

    def _resolve_ticket(self, shop: Shop, ticket_id: str) -> None:
        ticket = shop.tickets.get(ticket_id)
        if ticket is None:
            self._send(404, {"error": f"no such ticket {ticket_id!r}"})
        elif ticket["status"] != "open":
            self._send(409, {"error": f"ticket {ticket_id} is already {ticket['status']}"})
        else:
            scenario = Scenario(id=f"ticket-{ticket_id}", module=0, ticket_id=ticket_id, steps=[])
            self._send(200, _result_body(shop, run(scenario, RuleModel(), shop)))


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str, port: int) -> None:
    server = make_server(host, port)
    print(f"refund-bot listening on http://{host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
