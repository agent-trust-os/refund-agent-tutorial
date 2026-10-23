#!/usr/bin/env bash
# The whole story in one command: start the stack, a customer writes in, the agent resolves the ticket,
# and you see every tool call and what changed in the database and in Mailpit.     ./demo.sh
set -euo pipefail
cd "$(dirname "$0")"

API=http://localhost:8000
say()  { printf '\n\033[1m== %s\033[0m\n' "$1"; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); $1"; }

say "1. Start Postgres, Mailpit and the app"
docker compose up -d --build --wait >/dev/null 2>&1
docker compose ps --format '   {{.Service}}: {{.Status}}'

say "2. A customer writes in"
BODY='My mug arrived chipped and three days late. Can I get $25 back?'
echo "   customer C-1, order O-1001: \"$BODY\""
TICKET=$(curl -s -X POST $API/tickets -H Content-Type:application/json \
  -d "{\"customer_id\":\"C-1\",\"order_id\":\"O-1001\",\"body\":\"$BODY\"}" | json "print(d['ticket_id'])")
echo "   created $TICKET, status: $(curl -s $API/tickets/$TICKET | json "print(d['status'])")"

say "3. The agent resolves it, one tool at a time"
curl -s -X POST $API/tickets/$TICKET/resolve | json "
calls = {}
for m in d['transcript']:
    if m['role'] == 'assistant' and isinstance(m['content'], dict):
        calls[m['tool_call_id']] = m['content']
    elif m['role'] == 'tool':
        c = calls[m['tool_call_id']]
        print('   ' + c['tool'] + ' ' + json.dumps(c['args'])[:80])
        print('      -> ' + json.dumps(m['content'])[:90])
print('   agent says: ' + d['answer'])"

say "4. What changed"
curl -s $API/tickets | json "
for t in d:
    if t['ticket_id'] >= '$TICKET':
        print('   ticket ' + t['ticket_id'] + ': ' + t['status'] + ('  - ' + t['note'] if t['note'] else '  - ' + t['body'][:50]))"
curl -s $API/refunds | json "
for r in d:
    if r['ticket_id'] == '$TICKET': print('   refund ' + r['refund_id'] + ': \$' + str(r['amount']) + ' on ' + r['order_id'])"
curl -s "$API/actions?ticket_id=$TICKET" | json "print('   action log: ' + str(len(d)) + ' tool calls recorded')"
echo "   email in Mailpit: $(curl -s localhost:8025/api/v1/messages | json "m = d['messages'][0]; print(m['To'][0]['Address'] + ' | ' + m['Subject'])")"

say "Look around"
echo "   API docs (try every endpoint):  $API/docs"
echo "   Mailpit (the email):            http://localhost:8025"
echo "   Start over:                     curl -X POST $API/reset"
echo "   Stop:                           docker compose down -v"
