#!/usr/bin/env python3
"""Print a ticket run (the JSON from POST /tickets/<id>/resolve) as short, readable lines.

    curl -s -X POST "localhost:8000/tickets/T-1003/resolve?governed=harness" | python3 scripts/show_run.py
"""
import json
import sys

run = json.load(sys.stdin)
for message in run["transcript"]:
    content = message["content"]
    if message["role"] == "assistant" and isinstance(content, dict):
        print("call  ", content["tool"], json.dumps(content["args"])[:100])
    elif message["role"] == "tool":
        print("result", json.dumps(content)[:170])
print("answer", run["answer"])
print("ticket", run["ticket"]["status"], "|", run["ticket"]["note"])
print("actions", [action["tool"] for action in run["actions"]])
