#!/usr/bin/env bash
# Replay the harness article from a clean clone of the template, step by step.
#   docs/guides/verify/harness.sh            offline: stub gateway only
#   docs/guides/verify/harness.sh --live     also run the tickets against the gateway in python/.env
# Prints "step N ok" and stops at the first mismatch.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
TEMPLATE_REF="${TEMPLATE_REF:-feat/postgres-mailpit}"
SOLUTION_REF="${SOLUTION_REF:-solution}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"; pkill -f "refund-bot serve --port 8799" 2>/dev/null || true' EXIT
step() { echo "step $1 ok  ($2)"; }
fail() { echo "FAIL step $1: $2" >&2; exit 1; }

git clone -q --branch "$TEMPLATE_REF" "$REPO" "$WORK/app"; cd "$WORK/app"
step 1 "cloned the template"
[ "$(./scripts/todos.sh | head -1)" = "0 of 10 done" ] || fail 2 "template should start with 0 of 10 done"
(cd python && uv run --quiet pytest -q >/dev/null 2>&1) || fail 2 "template tests fail"
step 2 "template runs, 0 of 10 done, tests pass"

python3 docs/guides/apply_snippets.py --only 1-6 >/dev/null
[ "$(./scripts/todos.sh | head -1)" = "6 of 10 done" ] || fail 3 "expected 6 of 10 done"
step 3 "applied the snippets of TODOs 1 to 6: 6 of 10 done"

# the replay equals the solution branch, file by file (tests and snippet tooling aside)
git fetch -q "$REPO" "$SOLUTION_REF"
for f in $(git diff --name-only); do
  git diff --quiet FETCH_HEAD -- "$f" || fail 4 "$f differs from $SOLUTION_REF"
done
step 4 "the touched files equal the $SOLUTION_REF branch"

git checkout -q FETCH_HEAD -- python/tests/test_harness_governed.py python/uv.lock
(cd python && uv sync --quiet 2>/dev/null && uv run --quiet pytest -q 2>&1 | tail -1 | grep -q passed) || fail 5 "tests with the TODOs filled in fail"
step 5 "tests pass against the stub gateway (blocks, fail closed, no PII)"

python3 "$REPO/docs/guides/build.py" --check || fail 6 "harness.html is out of date"
step 6 "harness.html matches its snippets and outputs"

if [ "${1:-}" = "--live" ]; then
  [ -f "$REPO/python/.env" ] || fail 7 "no python/.env for --live"
  cp "$REPO/python/.env" python/.env
  (cd python && uv run --quiet refund-bot agenttrust check | grep -c '^ok' | grep -qx 4) || fail 7 "agenttrust check is not 4 ticks"
  step 7 "agenttrust check: 4 ticks"
  export DATABASE_URL="sqlite:///$WORK/live.db"
  (cd python && uv run --quiet refund-bot reset >/dev/null && (uv run --quiet refund-bot serve --port 8799 >"$WORK/serve.log" 2>&1 &)); sleep 5
  resolve() { curl -s -X POST "localhost:8799/tickets/$1/resolve?governed=harness"; }
  assert() { python3 -c "import json,sys; d=json.load(sys.stdin); $1" || fail 8 "$2"; }
  resolve T-1001 | assert "assert d['ticket']['status']=='resolved' and 'issue_refund' in [a['tool'] for a in d['actions']]" "T-1001 should be refunded"
  resolve T-1003 | assert "assert d['ticket']['status']=='escalated' and 'issue_refund' not in [a['tool'] for a in d['actions']] and any(m['content'].get('status')=='BLOCKED' for m in d['transcript'] if m['role']=='tool')" "T-1003 should be blocked"
  resolve T-1005 | assert "assert 'purge_orders' not in [a['tool'] for a in d['actions']] and d['ticket']['status']=='escalated'" "T-1005 should be blocked"
  resolve T-1002 | assert "assert 'issue_refund' not in [a['tool'] for a in d['actions']]" "T-1002 should be blocked by the pack"
  resolve T-1004 | assert "assert any(m['content'].get('tool')=='read_ticket' and m['content'].get('status')=='BLOCKED' for m in d['transcript'] if m['role']=='tool')" "T-1004 read should be withheld"
  step 8 "live: refund allowed; \$5,000, purge and \$900 blocked; injected ticket withheld"
fi
echo "all steps ok"
