"""A small HTTP server so the Refund Bot runs as a service (``docker compose up``).

Standard library only. Each ``POST /run/<scenario>`` plays the scenario on a fresh shop and returns
the transcript and the shop's action log, so a request shows what really ran.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from refund_core.models.mock import MockModel
from refund_core.scenarios import BY_ID, SCENARIOS
from refund_core.shop import Shop

from .agent import run

ENDPOINTS = ["GET /health", "GET /scenarios", "POST /run/{scenario}"]


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: Any) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        elif self.path == "/scenarios":
            self._send(200, [{"id": s.id, "module": s.module, "ticket_id": s.ticket_id} for s in SCENARIOS])
        elif self.path == "/":
            self._send(200, {"app": "refund-bot", "endpoints": ENDPOINTS})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        prefix = "/run/"
        if not self.path.startswith(prefix):
            self._send(404, {"error": "not found"})
            return
        scenario_id = self.path[len(prefix):]
        scenario = BY_ID.get(scenario_id)
        if scenario is None:
            self._send(404, {"error": f"unknown scenario {scenario_id!r}"})
            return
        result = run(scenario, MockModel(scenario), Shop())
        self._send(200, {
            "scenario": scenario.id,
            "answer": result.answer,
            "transcript": [asdict(m) for m in result.transcript],
            "actions": result.actions,
        })


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
