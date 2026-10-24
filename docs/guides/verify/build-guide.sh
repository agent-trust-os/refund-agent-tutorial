#!/usr/bin/env bash
# Replay the "Build a Governed Refund Bot" guide against the solution branch.
#   docs/guides/verify/build-guide.sh [--live]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"; pkill -f "refund-bot serve --port 8798" 2>/dev/null || true' EXIT
step() { echo "step $1 ok  ($2)"; }
fail() { echo "FAIL step $1: $2" >&2; exit 1; }

git clone -q --branch solution "$REPO" "$WORK/app"; cd "$WORK/app/python"
step 1 "cloned the solution branch"
[ "$(../scripts/todos.sh | head -1)" = "7 of 11 done" ] || fail 2 "solution should have TODOs 1 to 7 done"
uv sync --quiet 2>/dev/null; uv run --quiet pytest -q 2>&1 | tail -1 | grep -q passed || fail 2 "tests fail"
step 2 "tests pass (blocks, fail closed, no PII, against the stub gateway)"
python3 "$REPO/docs/guides/build.py" --check || fail 3 "build-governed-refund-bot.html is out of date"
step 3 "every code block in the guide equals the solution branch"
if [ "${1:-}" = "--live" ]; then
  [ -f "$REPO/python/.env" ] || fail 4 "no python/.env for --live"
  cp "$REPO/python/.env" .env
  uv run --quiet refund-bot agenttrust check | grep -c '^ok' | grep -qx 4 || fail 4 "agenttrust check is not 4 ticks"
  step 4 "agenttrust check: 4 ticks"
  export DATABASE_URL="sqlite:///$WORK/live.db"
  uv run --quiet refund-bot reset >/dev/null; (uv run --quiet refund-bot serve --port 8798 >"$WORK/serve.log" 2>&1 &); sleep 5
  post() { curl -s -X POST "localhost:8798/tickets/$1/resolve$2"; }
  post T-1003 "" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'issue_refund' in [a['tool'] for a in d['actions']]" || fail 5 "ungoverned should pay"
  post T-1005 "?governed=harness" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'purge_orders' not in [a['tool'] for a in d['actions']] and d['ticket']['status']=='escalated'" || fail 5 "governed purge should be blocked"
  step 5 "live: ungoverned bot pays \$5,000; governed bot blocks the purge and escalates"
fi
echo "all steps ok"
