#!/data/data/com.termux/files/usr/bin/bash
# อัปเดต GitHub Pages redirect ให้ตรงกับ tunnel URL ล่าสุด (เรียกจาก watchdog)

TUNNEL_LOG="$HOME/qchain-website/tunnel.log"
GHPAGES_DIR="$HOME/dynax-gh-pages"
LOG_FILE="$HOME/qchain-website/gh_pages_update.log"

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

LATEST_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | tail -1)

if [ -z "$LATEST_URL" ]; then
    log_msg "ไม่พบ URL ล่าสุด"
    exit 1
fi

CURRENT_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$GHPAGES_DIR/index.html" | head -1)

if [ "$LATEST_URL" == "$CURRENT_URL" ]; then
    exit 0
fi

log_msg "URL เปลี่ยน: $CURRENT_URL -> $LATEST_URL"

cd "$GHPAGES_DIR" || exit 1

python3 << PYEOF
content = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>DYNAX - Redirecting...</title>
<script>
  window.location.href = "$LATEST_URL";
</script>
</head>
<body>
<p>Redirecting to DYNAX... <a id="link" href="$LATEST_URL">Click here if not redirected</a></p>
</body>
</html>
"""
with open('index.html', 'w') as f:
    f.write(content)
PYEOF

git add index.html
git commit -m "Auto-update tunnel URL" >> "$LOG_FILE" 2>&1
git push origin gh-pages >> "$LOG_FILE" 2>&1

log_msg "อัปเดตสำเร็จ: $LATEST_URL"
