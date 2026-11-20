#!/usr/bin/env bash
# Print the current DDHT links.
cd "$(dirname "$0")"
if [ -s logs/public-url.txt ]; then
  echo "Public link:  $(cat logs/public-url.txt)"
else
  echo "Public link:  not available right now (starting up, offline, or ./start.sh not running)"
fi
for IFACE in en0 en1 en2; do
  IP="$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)"
  [ -n "$IP" ] && echo "Same Wi-Fi:   http://$IP:5174" && break
done
echo "This laptop:  http://localhost:5174"
