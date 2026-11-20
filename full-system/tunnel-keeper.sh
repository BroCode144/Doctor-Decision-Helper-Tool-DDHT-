#!/usr/bin/env bash
# Keeps the free Cloudflare quick tunnel alive (started by ./start.sh).
#
# Quick tunnels are temporary: if the laptop loses its connection for a while,
# Cloudflare deletes the tunnel and its link stops working for good
# ("Tunnel not found"). This loop notices that, starts a new tunnel, saves the
# NEW link to logs/public-url.txt and shows a macOS notification with it.

cd "$(dirname "$0")"
LOGS="logs"
mkdir -p "$LOGS"

notify() {
  osascript -e "display notification \"$1\" with title \"DDHT public link\"" >/dev/null 2>&1 || true
}

while true; do
  : >"$LOGS/tunnel.log"
  cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:5174 </dev/null >>"$LOGS/tunnel.log" 2>&1 &
  CF=$!
  echo "$CF" >"$LOGS/cloudflared.pid"

  URL=""
  for _ in $(seq 1 60); do
    URL="$(grep -oE 'https://[a-z0-9]+(-[a-z0-9]+)+\.trycloudflare\.com' "$LOGS/tunnel.log" | head -1 || true)"
    [ -n "$URL" ] && break
    kill -0 "$CF" 2>/dev/null || break
    sleep 1
  done

  if [ -n "$URL" ]; then
    echo "$URL" >"$LOGS/public-url.txt"
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $URL" >>"$LOGS/public-url-history.txt"
    notify "$URL"
    # Watch for Cloudflare deleting the tunnel, or cloudflared exiting.
    while kill -0 "$CF" 2>/dev/null; do
      if grep -q "Tunnel not found" "$LOGS/tunnel.log"; then
        echo "$(date '+%Y-%m-%d %H:%M:%S')  tunnel expired; opening a new link" >>"$LOGS/public-url-history.txt"
        break
      fi
      sleep 15
    done
  fi

  # No link (e.g. no internet) or tunnel lost: clean up and try again shortly.
  kill "$CF" 2>/dev/null || true
  rm -f "$LOGS/public-url.txt"
  sleep 10
done
