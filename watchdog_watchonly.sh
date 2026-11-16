#!/data/data/com.termux/files/usr/bin/bash
LOG="$HOME/dynax-skill/watchdog_watchonly.log"

log_msg() {
  echo "$(date '+%m-%d %H:%M') $1" >> "$LOG"
}

while true; do
  # cloudflared ยังอยู่ไหม
  if pgrep -f "cloudflared" >/dev/null; then
    CF_OK=1
  else
    CF_OK=0
  fi

  # URL ล่าสุดใน live_tunnel_url
  LURL=$(cat "$HOME/dynax-skill/live_tunnel_url" 2>/dev/null || echo missing)

  log_msg "cf=$CF_OK url=$LURL"
  sleep 30
done
