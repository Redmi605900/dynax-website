#!/data/data/com.termux/files/usr/bin/bash
# ==========================================================
# DYNAX NODE SECURITY & HEALTH CHECK v2.0
# Author : ChatGPT
# ==========================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PORT=${PORT:-6001}
REMOTE=https://dynax-node2.onrender.com

echo "======================================================"
echo "        DYNAX NODE SECURITY CHECK v2.0"
echo "======================================================"

echo
echo -e "${BLUE}[1] Process${NC}"
if pgrep -f dynax_node_v20.py >/dev/null; then
    echo -e "${GREEN}OK${NC} Node running"
    pgrep -af dynax_node_v20.py
else
    echo -e "${RED}FAIL${NC} Node not running"
fi

echo
echo -e "${BLUE}[2] Listening Port${NC}"
if command -v ss >/dev/null; then
    ss -ltn | grep ":$PORT " || echo "Port $PORT not listening"
else
    netstat -ltn 2>/dev/null | grep ":$PORT " || echo "Port $PORT not listening"
fi

echo
echo -e "${BLUE}[3] Important Files${NC}"
for f in dynax_chain.json peers.json genesis.json dynax.db event_logs.json liquidity_pool.json
do
    if [ -f "$f" ]; then
        echo -e "${GREEN}OK${NC} $f"
        sha256sum "$f"
    else
        echo -e "${YELLOW}WARN${NC} Missing $f"
    fi
done

echo
echo -e "${BLUE}[4] Chain Integrity${NC}"
python3 <<'PY'
import json,hashlib,os,sys

if not os.path.exists("dynax_chain.json"):
    print("Chain file missing")
    sys.exit()

chain=json.load(open("dynax_chain.json"))

print("Blocks :",len(chain))

ok=True

for i,b in enumerate(chain):

    if i>0:
        if b["prev_hash"]!=chain[i-1]["hash"]:
            print("Broken prev_hash at",i)
            ok=False
            break

    tmp=dict(b)
    h=tmp.pop("hash")

    calc=hashlib.sha3_256(
        json.dumps(tmp,sort_keys=True).encode()
    ).hexdigest()

    if calc!=h:
        print("Hash mismatch block",i)
        ok=False
        break

if ok:
    print("Chain integrity OK")
PY

echo
echo -e "${BLUE}[5] Local API${NC}"
curl -s http://127.0.0.1:$PORT/ | python3 -m json.tool 2>/dev/null || echo "Node offline"

echo
echo -e "${BLUE}[6] Local Stats${NC}"
curl -s http://127.0.0.1:$PORT/stats | python3 -m json.tool 2>/dev/null

echo
echo -e "${BLUE}[7] Remote Stats${NC}"
curl -s $REMOTE/stats | python3 -m json.tool 2>/dev/null

echo
echo -e "${BLUE}[8] Sync Check${NC}"

LOCAL=$(curl -s http://127.0.0.1:$PORT/stats | python3 -c "import sys,json;print(json.load(sys.stdin)['blocks'])" 2>/dev/null)

REMOTE_BLOCKS=$(curl -s $REMOTE/stats | python3 -c "import sys,json;print(json.load(sys.stdin)['blocks'])" 2>/dev/null)

echo "Local Blocks : $LOCAL"
echo "Remote Blocks: $REMOTE_BLOCKS"

if [ "$LOCAL" = "$REMOTE_BLOCKS" ]; then
    echo -e "${GREEN}SYNC OK${NC}"
else
    echo -e "${YELLOW}SYNC WARNING${NC}"
fi

echo
echo -e "${BLUE}[9] Peers${NC}"
curl -s http://127.0.0.1:$PORT/peers | python3 -m json.tool 2>/dev/null

echo
echo -e "${BLUE}[10] Genesis Hash${NC}"
python3 <<'PY'
import json,os
if os.path.exists("dynax_chain.json"):
    c=json.load(open("dynax_chain.json"))
    print(c[0]["hash"])
PY

echo
echo -e "${BLUE}[11] Chain Size${NC}"
ls -lh dynax_chain.json 2>/dev/null

echo
echo -e "${BLUE}[12] Database${NC}"
for f in dynax.db event_logs.json liquidity_pool.json
do
    [ -f "$f" ] && ls -lh "$f"
done

echo
echo -e "${BLUE}[13] Backups${NC}"
if [ -d backups ]; then
    ls -lh backups | tail
else
    echo "No backup directory"
fi

echo
echo -e "${BLUE}[14] Recent Errors${NC}"
tail -30 node.log 2>/dev/null | grep -Ei "error|exception|traceback" || echo "No recent errors"

echo
echo -e "${BLUE}[15] Disk Usage${NC}"
df -h .

echo
echo -e "${BLUE}[16] Memory${NC}"
free -h 2>/dev/null || head /proc/meminfo

echo
echo -e "${BLUE}[17] CPU Load${NC}"
uptime

echo
echo -e "${BLUE}[18] Cron Jobs${NC}"
crontab -l 2>/dev/null || echo "No cron jobs"

echo
echo -e "${BLUE}[19] Network Test${NC}"
ping -c 2 8.8.8.8 >/dev/null 2>&1 && echo "Internet OK" || echo "Internet FAILED"

echo
echo -e "${BLUE}[20] Latest Block${NC}"
python3 <<'PY'
import requests
try:
    c=requests.get("https://dynax-node2.onrender.com/chain",timeout=10).json()
    b=c[-1]
    print("Height :",len(c))
    print("Index  :",b["index"])
    print("Hash   :",b["hash"])
    print("Prev   :",b["prev_hash"])
    print("TX     :",len(b.get("transactions",[])))
except Exception as e:
    print(e)
PY

echo
echo "======================================================"
echo "        DYNAX NODE STATUS CHECK COMPLETE"
echo "======================================================"

