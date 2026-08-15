#!/data/data/com.termux/files/usr/bin/bash
# DYNAX Node Watchdog - เช็คว่า node/tunnel ยังรันอยู่ไหม ถ้าตายให้เปิดใหม่

NODE_DIR="$HOME/qchain-website"
NODE_SCRIPT="run_both.py"
LOG_FILE="$NODE_DIR/watchdog.log"
CHECK_INTERVAL=10

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
        log_msg "Tunnel NOT running - running update_tunnel.sh..."
        cd "$NODE_DIR" || exit 1
        bash update_tunnel.sh >> "$NODE_DIR/tunnel.log" 2>&1
        log_msg "Tunnel restart + URL update done"
    fi

    if ! pgrep -x "tor" > /dev/null; then
        log_msg "Tor NOT running - restarting..."
        tor -f "$PREFIX/etc/tor/torrc" >> "$NODE_DIR/tor.log" 2>&1 &
        log_msg "Tor restarted with PID $!"
    fi

    sleep "$CHECK_INTERVAL"
done
