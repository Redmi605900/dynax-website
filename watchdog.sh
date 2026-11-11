#!/data/data/com.termux/files/usr/bin/bash
# DYNAX Node Watchdog v4 - stable mode with guarded tunnel restart.
NODE_DIR="$HOME/qchain-website"
NODE_SCRIPT="run_both.py"
LOG_FILE="$NODE_DIR/watchdog.log"
CHECK_INTERVAL=15
TUNNEL_COOLDOWN=120
TUNNEL_FILE="$HOME/dynax-skill/live_tunnel_url"

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

api_healthy() {
    curl -s --max-time 5 "localhost:6001/stats" 2>/dev/null | grep -q '"blocks"'
}

node_running() {
    pgrep -f "run_both\.py" >/dev/null 2>&1
}

current_tunnel_url() {
    if [ -f "$TUNNEL_FILE" ]; then
        cat "$TUNNEL_FILE"
    fi
}

tunnel_healthy() {
    local u
    u="$(current_tunnel_url)"
    [ -n "$u" ] || return 1
    curl -s --max-time 8 "$u/stats" 2>/dev/null | grep -q '"blocks"'
}

log_msg "Watchdog v4 started"
[ -f "$HOME/.dynax_env" ] && . "$HOME/.dynax_env"

LAST_TUNNEL_RESTART=0

while true; do
    if node_running; then
        if api_healthy; then
            log_msg "Node process running and API healthy"
        else
            log_msg "Node process running but API unhealthy - restarting node"
            pkill -f "run_both\.py" 2>/dev/null || true
            sleep 2
            cd "$NODE_DIR" || exit 1
            nohup python3 "$NODE_SCRIPT" >> "$NODE_DIR/node_output.log" 2>&1 &
            log_msg "Node restarted with PID $!"
        fi
    else
        if api_healthy; then
            log_msg "API healthy but node process not visible - skipping blind restart"
        else
            log_msg "Node NOT running and API unhealthy - restarting..."
            cd "$NODE_DIR" || exit 1
            nohup python3 "$NODE_SCRIPT" >> "$NODE_DIR/node_output.log" 2>&1 &
            log_msg "Node restarted with PID $!"
        fi
    fi

    if ! pgrep -f "cloudflared tunnel" >/dev/null; then
        NOW=$(date +%s)
        if [ $((NOW - LAST_TUNNEL_RESTART)) -ge "$TUNNEL_COOLDOWN" ]; then
            log_msg "Tunnel process NOT running - running guarded tunnel update"
            cd "$NODE_DIR" || exit 1
            bash "$NODE_DIR/update_tunnel_guarded.sh" >> "$NODE_DIR/tunnel.log" 2>&1
            log_msg "Guarded tunnel update finished"
            LAST_TUNNEL_RESTART=$(date +%s)
        else
            log_msg "Tunnel process missing but within cooldown - skipping restart"
        fi
    else
        if tunnel_healthy; then
            log_msg "Tunnel process running and live URL healthy"
        else
            NOW=$(date +%s)
            if [ $((NOW - LAST_TUNNEL_RESTART)) -ge "$TUNNEL_COOLDOWN" ]; then
                log_msg "Tunnel URL unhealthy - running guarded tunnel update"
                cd "$NODE_DIR" || exit 1
                bash "$NODE_DIR/update_tunnel_guarded.sh" >> "$NODE_DIR/tunnel.log" 2>&1
                log_msg "Guarded tunnel update finished"
                LAST_TUNNEL_RESTART=$(date +%s)
            else
                log_msg "Tunnel URL unhealthy but within cooldown - skipping restart"
            fi
        fi
    fi

    if ! pgrep -x "tor" >/dev/null; then
        log_msg "Tor NOT running - restarting..."
        tor -f "$PREFIX/etc/tor/torrc" >> "$NODE_DIR/tor.log" 2>&1 &
        log_msg "Tor restarted with PID $!"
        sleep 30
    fi

    sleep "$CHECK_INTERVAL"
done
