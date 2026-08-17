#!/data/data/com.termux/files/usr/bin/bash
MINER_ADDRESS="DXa5ae9ccc94279d4f52b4f4e694a5a3b2f4f5ece3"
while true; do
  curl -s http://localhost:6001/mine/$MINER_ADDRESS
  echo ""
  sleep 15
done
