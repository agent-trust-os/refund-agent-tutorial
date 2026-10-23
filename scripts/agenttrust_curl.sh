#!/usr/bin/env bash
# The three AgentTrust runtime calls with plain curl, using the values in python/.env.
#   ./scripts/agenttrust_curl.sh pre   issue_refund '{"order_id":"O-1001","amount":40,"currency":"USD","reason":"arrived late"}'
#   ./scripts/agenttrust_curl.sh post  <envelope_id> '{"refund":{"amount":40}}'
#   ./scripts/agenttrust_curl.sh validate "I refunded $40" 
set -euo pipefail
cd "$(dirname "$0")/../python"
set -a; . ./.env; set +a
AGENT="${AGENTRUST_AGENT_ID:-refund-bot}"
call() {  # path, json body
  curl -sS -X POST "$AGENTRUST_GATEWAY_URL/v1/runtime/$1" \
    -H "Authorization: Bearer $AGENTRUST_KEY" -H "Content-Type: application/json" -d "$2"
  echo
}
case "${1:-}" in
  pre)  call pre-check "{\"agent_id\":\"$AGENT\",\"framework\":\"REST\",\"action\":\"$2\",\"params\":$3,\"user\":\"support-bot\",\"input\":\"\",\"model\":\"mock\"}" ;;
  post) call post-check "{\"pre_check_envelope_id\":\"$2\",\"execution\":{\"model\":\"mock\",\"tools_called\":[],\"tool_results\":[],\"latency_ms\":0,\"tokens\":0},\"output\":$3}" ;;
  validate) call validate "{\"agent_id\":\"$AGENT\",\"framework\":\"REST\",\"request\":{\"user\":\"support-bot\",\"input\":\"\"},\"execution\":{\"model\":\"mock\",\"tools_called\":[],\"tool_results\":[]},\"output\":{\"text\":\"$2\"}}" ;;
  *) echo "usage: $0 pre|post|validate ..." >&2; exit 2 ;;
esac
