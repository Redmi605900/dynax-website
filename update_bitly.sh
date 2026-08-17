#!/data/data/com.termux/files/usr/bin/bash
# อัปเดต Bitly link ให้ชี้ไป tunnel URL ล่าสุด

TOKEN_FILE="$HOME/qchain-website/bitly_token.txt"
TUNNEL_LOG="$HOME/qchain-website/tunnel.log"
BITLY_ID="bit.ly/4fqOnOn"

if [ ! -f "$TOKEN_FILE" ]; then
    echo "ไม่พบไฟล์ token: $TOKEN_FILE"
    exit 1
fi

TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')
LATEST_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | tail -1)

if [ -z "$LATEST_URL" ]; then
    echo "ไม่พบ URL ล่าสุดใน tunnel.log"
    exit 1
fi

echo "กำลังอัปเดต $BITLY_ID -> $LATEST_URL"

curl -s -X PATCH "https://api-ssl.bitly.com/v4/bitlinks/$BITLY_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"long_url\": \"$LATEST_URL\"}"

echo ""
echo "อัปเดตเสร็จแล้ว"
