#!/usr/bin/env bash
# One command, whole story: start the stack, a customer writes in, the agent resolves the ticket,
# and you see what changed in the app, in Postgres and in Mailpit.   ./demo.sh
set -euo pipefail
cd "$(dirname "$0")"

API=http://localhost:8000
say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
field() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }

say "1. Start Postgres, Mailpit and the app"
docker compose up -d --build --wait >/dev/null 2>&1
docker compose ps --format '   {{.Service}}: {{.Status}}'

say "2. Open a workspace (its own copy of the shop)"
RUN=$(curl -s -X POST $API/runs | field "d['run_id']")
echo "   run_id: $RUN"

say "3. A customer writes in"
BODY='My mug arrived chipped and three days late. Can I get $25 back?'
echo "   C-1 about order O-1001: \"$BODY\""
TICKET=$(curl -s -X POST $API/runs/$RUN/tickets -H Content-Type:application/json \
  -d "{\"customer_id\":\"C-1\",\"order_id\":\"O-1001\",\"body\":\"$BODY\"}" | field "d['ticket']['ticket_id']")
echo "   created $TICKET, status: $(curl -s $API/runs/$RUN/tickets/$TICKET | field "d['ticket']['status']")"

say "4. The agent resolves it"
curl -s -X POST $API/runs/$RUN/tickets/$TICKET/resolve | field "
'\n'.join(
  ('   call   ' + m['content']['tool'] + ' ' + str(m['content']['args'])[:70]) if m['role']=='assistant' and isinstance(m['content'], dict)
  else ('   said   ' + m['content']) if m['role']=='assistant' else ''
  for m in d['transcript'] if m['role']=='assistant')"

say "5. What changed"
curl -s $API/runs/$RUN | field "
'\n'.join(['   ticket ' + t['ticket_id'] + ': ' + t['status'] + ('  - ' + t['note'] if t['note'] else '')
           for t in d['tickets'].values() if t['ticket_id'] >= 'T-1006'] +
          ['   refund  ' + r['refund_id'] + ': \$' + str(r['amount']) + ' on ' + r['order_id'] for r in d['refunds']])"
echo "   email in Mailpit: $(curl -s localhost:8025/api/v1/messages | field "d['messages'][0]['To'][0]['Address'] + ' | ' + d['messages'][0]['Subject']")"
echo "   rows in Postgres:"
docker compose exec -T postgres psql -U refund -d refund -c \
  "select ticket_id, status, note from tickets where run_id='$RUN' and ticket_id >= 'T-1006' order by 1" | sed 's/^/   /'

say "Look around"
echo "   Mailpit (the email):  http://localhost:8025"
echo "   Whole workspace:      curl -s $API/runs/$RUN"
echo "   Stop:                 docker compose down -v"
