#!/usr/bin/env bash
# Start DDHT and share it.
#
#   ./start.sh            start everything + public HTTPS link (Cloudflare quick tunnel)
#   ./start.sh --no-tunnel  start everything for this Wi-Fi / this laptop only
#   ./stop.sh             stop everything
#
# Everything (PostgreSQL, API, vector store, uploaded files) stays on this laptop.
# Only the web app (port 5174) is exposed: to the Wi-Fi, and through the tunnel.
# The API (port 8000) and PostgreSQL are private; the web server forwards /api
# to the API internally.

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"
TUNNEL=1
[ "${1:-}" = "--no-tunnel" ] && TUNNEL=0

say() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
fail() { printf '\033[1;31mERROR:\033[0m %s\n' "$1"; exit 1; }

# 1. PostgreSQL ---------------------------------------------------------------
if ! pg_isready -q; then
  say "Starting PostgreSQL..."
  brew services start postgresql@18 >/dev/null 2>&1 || true
  for _ in $(seq 1 15); do pg_isready -q && break; sleep 1; done
fi
pg_isready -q || fail "PostgreSQL is not running. Try: brew services restart postgresql@18"

# 2. Stop anything already running ----------------------------------------------
"$ROOT/stop.sh" --quiet || true

# 3. Backend API (private: 127.0.0.1 only) ------------------------------------
say "Starting the backend API..."
(
  cd "$ROOT/backend"
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips 127.0.0.1 </dev/null >"$LOGS/backend.log" 2>&1 &
)
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8000/health >/dev/null && break; sleep 1; done
HEALTH="$(curl -sf http://127.0.0.1:8000/health)" || fail "Backend did not start. See $LOGS/backend.log"

# 4. Frontend: production build, served on the network ------------------------
say "Building the web app..."
(cd "$ROOT/frontend" && npm run build >"$LOGS/frontend-build.log" 2>&1) || fail "Build failed. See $LOGS/frontend-build.log"
say "Starting the web server..."
(cd "$ROOT/frontend" && nohup npm run preview </dev/null >"$LOGS/frontend.log" 2>&1 &)
for _ in $(seq 1 20); do curl -sf -o /dev/null http://127.0.0.1:5174/ && break; sleep 1; done
curl -sf -o /dev/null http://127.0.0.1:5174/ || fail "Web server did not start. See $LOGS/frontend.log"

# 5. Public HTTPS link (Cloudflare quick tunnel, free, no account) -------------
PUBLIC_URL=""
rm -f "$LOGS/public-url.txt"
if [ "$TUNNEL" = "1" ]; then
  command -v cloudflared >/dev/null || fail "cloudflared is not installed. Run: brew install cloudflared"
  say "Opening the public link (Cloudflare tunnel)..."
  # The keeper starts cloudflared and replaces the tunnel if Cloudflare ever drops it.
  nohup "$ROOT/tunnel-keeper.sh" </dev/null >/dev/null 2>&1 &
  echo $! >"$LOGS/tunnel.pid"
  for _ in $(seq 1 60); do
    PUBLIC_URL="$(cat "$LOGS/public-url.txt" 2>/dev/null || true)"
    [ -n "$PUBLIC_URL" ] && break
    sleep 1
  done
  if [ -n "$PUBLIC_URL" ]; then
    # Wait until the new address is reachable (DNS can take a few seconds).
    for _ in $(seq 1 30); do curl -sf -o /dev/null -m 5 "$PUBLIC_URL/" && break; sleep 2; done
  fi
fi

# 6. Keep the Mac awake while sharing ------------------------------------------
nohup caffeinate -dims </dev/null >/dev/null 2>&1 &
echo $! >"$LOGS/caffeinate.pid"

# 7. Print the links --------------------------------------------------------------
IP=""
for IFACE in en0 en1 en2 en3 en4 en5; do
  IP="$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)"
  [ -n "$IP" ] && break
done
AI="$(printf '%s' "$HEALTH" | python3 -c 'import sys,json; h=json.load(sys.stdin); print(("ON  (" + h["llm_provider"] + ": " + h["llm_model"] + ")") if h["ai_configured"] else "OFF (no API key set in backend/.env)")')"

echo
echo "------------------------------------------------------------------"
echo " DDHT is running."
echo
if [ "$TUNNEL" = "1" ]; then
  if [ -n "$PUBLIC_URL" ]; then
    echo "   PUBLIC LINK (any network):  $PUBLIC_URL"
    echo "                               (see the current link any time with: ./link.sh)"
  else
    echo "   Public link could not be created. See $LOGS/tunnel.log"
  fi
fi
[ -n "$IP" ] && echo "   Same Wi-Fi:                 http://$IP:5174"
echo "   On this laptop:             http://localhost:5174"
echo
echo "   AI: $AI"
echo "   Logs: $LOGS"
echo
echo " Keep this laptop on and plugged in with the lid OPEN (locking is fine)."
echo " The public link changes every time you run ./start.sh, and if Cloudflare"
echo " drops it (e.g. after a long network outage) a new one is opened automatically:"
echo " you'll get a Mac notification, and ./link.sh always shows the current one."
echo " Stop with: ./stop.sh"
echo "------------------------------------------------------------------"
