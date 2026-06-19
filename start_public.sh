#!/bin/bash

echo "🚀 เปิด DYNAX บน Internet..."
echo ""

# เปิด Block Explorer
echo "📦 Block Explorer (Port 6006)..."
lt --port 6006 --subdomain dynax-explorer > $HOME/lt-explorer.log 2>&1 &
sleep 3

# เปิด Mobile App
echo "📱 Mobile App (Port 6007)..."
lt --port 6007 --subdomain dynax-mobile > $HOME/lt-mobile.log 2>&1 &
sleep 3

# เปิด DEX
echo "💱 DEX (Port 6004)..."
lt --port 6004 --subdomain dynax-dex > $HOME/lt-dex.log 2>&1 &
sleep 3

# เปิด DVM
echo "🧠 DVM (Port 6005)..."
lt --port 6005 --subdomain dynax-dvm > $HOME/lt-dvm.log 2>&1 &
sleep 3

# เปิด Node
echo "⛏️ Node (Port 6002)..."
lt --port 6002 --subdomain dynax-node > $HOME/lt-node.log 2>&1 &
sleep 3

echo ""
echo "================================"
echo "🌐 DYNAX Online แล้ว!"
echo "================================"
echo ""
echo "📱 Public URLs:"
echo ""
echo "Block Explorer:"
grep -o 'https://[^ ]*loca.lt' $HOME/lt-explorer.log | head -1
echo ""
echo "Mobile App:"
grep -o 'https://[^ ]*loca.lt' $HOME/lt-mobile.log | head -1
echo ""
echo "DEX:"
grep -o 'https://[^ ]*loca.lt' $HOME/lt-dex.log | head -1
echo ""
echo "DVM:"
grep -o 'https://[^ ]*loca.lt' $HOME/lt-dvm.log | head -1
echo ""
echo "Node:"
grep -o 'https://[^ ]*loca.lt' $HOME/lt-node.log | head -1
echo ""
echo "================================"
echo ""
echo "หยุด services: pkill -f lt"
