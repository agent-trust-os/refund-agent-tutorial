"""A tiny AgentTrust gateway for offline tests: same paths and response shape as the real runtime routes.

Rules: a wrong key is HTTP 401; ``purge_orders`` is not declared (block); ``issue_refund`` above 1000 is
blocked by the manifest cap; everything else is approved. Every request is kept in ``seen``.
"""
from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

GOOD_KEY = "at_live_" + "0" * 32


class StubGateway:
    def __init__(self) -> None:
        self.seen: list[dict] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _send(self, status: int, body: dict) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                self._send(200, {"status": "ok"})

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.seen.append({"path": self.path, **body})
                if self.headers.get("X-AgentTrust-Token") != GOOD_KEY:
                    return self._send(401, {"detail": "invalid key"})
                outcome, reason = "approve", "within policy"
                if self.path.endswith("/pre-check"):
                    if body["action"] == "purge_orders":
                        outcome, reason = "block", "tool_trust: undeclared tool"
                    elif body["action"] == "issue_refund" and body["params"].get("amount", 0) > 1000:
                        outcome, reason = "block", "tool_trust: amount above max_amount"
                self._send(200, {"envelope_id": str(uuid.uuid4()), "latency_ms": 1.0, "risk": {},
                                 "validation": {}, "decision": {"outcome": outcome, "reason": reason}})

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
