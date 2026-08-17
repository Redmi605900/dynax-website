#!/data/data/com.termux/files/usr/bin/bash

BACKUP_DIR="$HOME/dynax-node2/backups"
DATE=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

cd "$HOME/dynax-node2" || exit 1

cp dynax_chain.json "$BACKUP_DIR/dynax_chain_$DATE.json" 2>/dev/null
cp peers.json "$BACKUP_DIR/peers_$DATE.json" 2>/dev/null
cp genesis.json "$BACKUP_DIR/genesis_$DATE.json" 2>/dev/null
cp dynax.db "$BACKUP_DIR/dynax_$DATE.db" 2>/dev/null
cp event_logs.json "$BACKUP_DIR/event_logs_$DATE.json" 2>/dev/null
cp liquidity_pool.json "$BACKUP_DIR/liquidity_pool_$DATE.json" 2>/dev/null

find "$BACKUP_DIR" -type f -mtime +7 -delete

echo "[$(date)] Backup completed."
