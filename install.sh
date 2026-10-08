#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=== DYNAX Node Installer ==="

P2P_SECRET_VALUE="dynax-local-secret-1791342341"

echo "[1/6] Installing dependencies..."
pkg update -y
pkg install -y python git openssh tor
pip install flask flask-cors requests ecdsa pysocks gunicorn

echo "[2/6] Cloning DYNAX..."
cd ~
if [ -d dynax-website ]; then
    echo "dynax-website already exists, pulling latest instead"
    cd dynax-website
    git pull
else
    git clone --depth 1 https://github.com/Redmi605900/dynax-website.git
    cd dynax-website
fi

echo "[3/6] Setting up P2P secret..."
echo "export P2P_SECRET=$P2P_SECRET_VALUE" > ~/.dynax_env
chmod 600 ~/.dynax_env

echo "[4/6] Setting up Tor hidden service..."
mkdir -p $PREFIX/var/lib/tor/dynax_hs
chmod 700 $PREFIX/var/lib/tor/dynax_hs
if ! grep -q "dynax_hs" $PREFIX/etc/tor/torrc; then
    printf '\nHiddenServiceDir %s/var/lib/tor/dynax_hs/\nHiddenServicePort 80 127.0.0.1:6001\n' "$PREFIX" >> $PREFIX/etc/tor/torrc
fi
pkill -x tor 2>/dev/null || true
sleep 2
tor -f $PREFIX/etc/tor/torrc > ~/tor.log 2>&1 &
echo "Waiting for Tor to generate your .onion address (up to 90s)..."
for i in $(seq 1 18); do
    sleep 5
    if [ -f "$PREFIX/var/lib/tor/dynax_hs/hostname" ]; then
        break
    fi
done
MY_ONION=$(cat $PREFIX/var/lib/tor/dynax_hs/hostname 2>/dev/null)
if [ -z "$MY_ONION" ]; then
    echo "ERROR: Tor did not generate an onion address in time. Run this script again."
    exit 1
fi
echo "Your node's address: $MY_ONION"

echo "[5/6] Starting your node..."
. ~/.dynax_env
pkill -f run_both.py 2>/dev/null || true
sleep 2
PORT=6001 MY_URL="http://$MY_ONION" nohup python3 run_both.py > ~/node.log 2>&1 &
sleep 10
curl -s localhost:6001/stats
echo ""

echo "[6/6] Connecting to the main DYNAX network..."
curl --max-time 90 -X POST -H "Content-Type: application/json" \
  -d '{"peer":"http://7elhinjau6eqcvbji4zitx2kb42njek5zitv6iwg6kkhup7qaclp5sqd.onion"}' \
  localhost:6001/peers/add
echo ""

echo "=== Done ==="
echo "Your node's onion address is: $MY_ONION"
echo "Send this to the network maintainer so they can connect back to you."
echo "Check sync progress anytime with: curl -s localhost:6001/stats"
