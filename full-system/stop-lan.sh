#!/usr/bin/env bash
# Stop the DDHT API (8000), web server (5174), public tunnel and keep-awake helper.
# PostgreSQL is left running (it uses almost no resources); all data is kept.

cd "$(dirname "$0")"
QUIET="${1:-}"

for PORT in 8000 5174; do
  PIDS="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null || true
  fi
done

# tunnel.pid = the keeper loop (stop it first so it doesn't start a new tunnel), then cloudflared.
for PIDFILE in logs/tunnel.pid logs/cloudflared.pid logs/caffeinate.pid; do
  if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi
done
rm -f logs/public-url.txt

sleep 1
[ "$QUIET" = "--quiet" ] || echo "DDHT stopped."
