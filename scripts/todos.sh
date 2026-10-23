#!/usr/bin/env bash
# Show which AgentTrust TODOs are still open. A TODO is done when its marker line is gone.
cd "$(dirname "$0")/.."
TOTAL=11
open=$(grep -rhoE 'TODO\(AgentTrust [0-9]+/11\)' python --include='*.py' --include='*.toml' --include='.env-sample' 2>/dev/null \
  | sed -E 's/.* ([0-9]+)\/11.*/\1/' | sort -un)
count=$(printf '%s\n' "$open" | grep -c . || true)
echo "$((TOTAL - count)) of $TOTAL done"
for n in $open; do
  echo "  open: $n  $(grep -rlE "TODO\(AgentTrust $n/11\)" python --include='*.py' --include='*.toml' | tr '\n' ' ')"
done
