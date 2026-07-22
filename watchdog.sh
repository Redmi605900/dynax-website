#!/data/data/com.termux/files/usr/bin/bash
# DYNAX Node Watchdog - เช็คว่า node ยังรันอยู่ไหม ถ้าตายให้เปิดใหม่

NODE_DIR="$HOME/qchain-website"
NODE_SCRIPT="run_both.py"
LOG_FILE="$NODE_DIR/watchdog.log"
CHECK_INTERVAL=30

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log_msg "Watchdog started"

MINER_ADDRESS="DXa5ae9ccc94279d4f52b4f4e694a5a3b2f4f5ece3"

while true; do
    if ! pgrep -f "$NODE_SCRIPT" > /dev/null; then
        log_msg "Node NOT running - restarting..."
        cd "$NODE_DIR" || exit 1
        nohup python3 "$NODE_SCRIPT" >> "$NODE_DIR/node_output.log" 2>&1 &
        log_msg "Node restarted with PID $!"
    fi

    if ! pgrep -f "cloudflared tunnel" > /dev/null; then
        log_msg "Tunnel NOT running - restarting..."
        cd "$NODE_DIR" || exit 1
        nohup cloudflared tunnel --protocol http2 --url http://localhost:6001 >> "$NODE_DIR/tunnel.log" 2>&1 &
        log_msg "Tunnel restarted with PID $!"
    fi

    if ! pgrep -f "automine_loop.sh" > /dev/null; then
        log_msg "Auto-mine NOT running - restarting..."
        cd "$NODE_DIR" || exit 1
        nohup bash automine_loop.sh >> "$NODE_DIR/automine.log" 2>&1 &
        log_msg "Auto-mine restarted with PID $!"
    fi

    cd "$NODE_DIR" || exit 1
    bash update_gh_pages.sh

    sleep "$CHECK_INTERVAL"
done
