#!/data/data/com.termux/files/usr/bin/bash
# update_tunnel.sh
# รีสตาร์ท Cloudflare Quick Tunnel, ดึง URL ใหม่, อัปเดตทุกไฟล์ HTML, commit + push อัตโนมัติ

set -e

WEBSITE_DIR="$HOME/qchain-website"
LOG_FILE="$HOME/cloudflared.log"
LOCAL_PORT=6001

echo "=============================================="
echo "  DYNAX Tunnel Auto-Updater"
echo "=============================================="

OLD_URL=$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$WEBSITE_DIR"/*.html 2>/dev/null | head -1 | cut -d: -f2-)
echo "URL เก่า (ถ้ามี): $OLD_URL"

echo ""
echo "[1/5] กำลังหยุด tunnel เก่า..."
pkill -9 -f "cloudflared tunnel" 2>/dev/null || true
sleep 2

echo "[2/5] กำลังเริ่ม tunnel ใหม่..."
cd "$HOME"
nohup cloudflared tunnel --protocol http2 --url "http://127.0.0.1:$LOCAL_PORT" > "$LOG_FILE" 2>&1 &
disown

echo "[3/5] กำลังรอ URL ใหม่..."
NEW_URL=""
for i in $(seq 1 15); do
    sleep 2
    NEW_URL=$(cat -v "$LOG_FILE" 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
    if [ -n "$NEW_URL" ]; then
        break
    fi
done

if [ -z "$NEW_URL" ]; then
    echo "❌ ไม่พบ URL ใหม่ใน log หลังรอ 30 วินาที ลองเช็ค $LOG_FILE ด้วยตนเอง"
    exit 1
fi

echo "✅ URL ใหม่: $NEW_URL"

echo "[4/5] กำลังทดสอบ URL ใหม่..."
sleep 5
STATUS=$(curl -sS --max-time 15 "$NEW_URL/chain" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
if [ "$STATUS" != "200" ]; then
    echo "⚠️  URL ใหม่ตอบสนองด้วย HTTP $STATUS (ไม่ใช่ 200) ตรวจสอบ node ว่ารันอยู่ที่ port $LOCAL_PORT หรือไม่"
    echo "    (จะดำเนินการอัปเดตไฟล์ต่อไปเผื่อ node ยังไม่พร้อมชั่วคราว)"
fi

echo "[5/5] กำลังอัปเดตไฟล์ HTML และ push..."
cd "$WEBSITE_DIR"
sed -i -E "s|https://[a-z0-9-]+\.trycloudflare\.com|$NEW_URL|g" *.html

CHANGED=$(git status --porcelain -- '*.html' | wc -l)
if [ "$CHANGED" -eq 0 ]; then
    echo "ไม่มีไฟล์เปลี่ยนแปลง (URL เดิมตรงกับใหม่อยู่แล้ว)"
else
    git add -- '*.html'
    git commit -m "Auto-update tunnel URL to $NEW_URL"
    git push origin main
    echo "✅ Push สำเร็จ: $NEW_URL"
fi

echo ""
echo "=============================================="
echo "  เสร็จสมบูรณ์"
echo "  URL ปัจจุบัน: $NEW_URL"
echo "=============================================="
