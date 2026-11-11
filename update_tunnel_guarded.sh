#!/data/data/com.termux/files/usr/bin/bash
# Guarded wrapper: only run update_tunnel.sh when live config is missing or unhealthy.
TUNNEL_FILE="$HOME/dynax-skill/live_tunnel_url"
CURRENT=""
[ -f "$TUNNEL_FILE" ] && CURRENT=$(cat "$TUNNEL_FILE")

if [ -n "$CURRENT" ] && curl -s --max-time 8 "$CURRENT/stats" 2>/dev/null | grep -q '"blocks"'; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - current tunnel URL healthy - skipping update_tunnel.sh"
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - current tunnel URL unhealthy or missing - running update_tunnel.sh"
bash "$HOME/qchain-website/update_tunnel.sh"
