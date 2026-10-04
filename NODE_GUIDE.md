# Running a DYNAX Node

This guide walks you through running a full DYNAX node with Tor (.onion) support, so it can sync with the main network without depending on a stable public IP or domain.

## Requirements
- Android phone (or any Linux machine with Termux/bash)
- Stable internet connection (test with `ping -c 10 github.com`, should show 0% packet loss)
- At least 500MB free storage

## Step 1: Install Termux
Install from F-Droid only (not Play Store, which is unsupported):
https://f-droid.org/packages/com.termux/

## Step 2: Install dependencies
pkg update -y
pkg install -y python git openssh tor
pip install flask flask-cors requests ecdsa pysocks gunicorn

## Step 3: Clone the code
cd ~
git clone --depth 1 https://github.com/Redmi605900/dynax-website.git
cd dynax-website

If git clone keeps failing (unstable connection), use this instead:
curl -L --retry 5 --retry-delay 3 -o dynax.zip https://github.com/Redmi605900/dynax-website/archive/refs/heads/main.zip
unzip dynax.zip && mv dynax-website-main dynax-website && cd dynax-website

## Step 4: Get the P2P secret
DM the network maintainer for the P2P_SECRET value (shared privately, never posted publicly). Then:
echo 'export P2P_SECRET=<value you received>' > ~/.dynax_env
chmod 600 ~/.dynax_env

## Step 5: Set up your Tor hidden service
This gives your node a stable .onion address that works even without a public IP.
mkdir -p $PREFIX/var/lib/tor/dynax_hs && chmod 700 $PREFIX/var/lib/tor/dynax_hs
printf '\nHiddenServiceDir %s/var/lib/tor/dynax_hs/\nHiddenServicePort 80 127.0.0.1:6001\n' "$PREFIX" >> $PREFIX/etc/tor/torrc
tor -f $PREFIX/etc/tor/torrc &
sleep 60
cat $PREFIX/var/lib/tor/dynax_hs/hostname

Save the .onion address this prints -- that is your node's address.

## Step 6: Start your node
cd ~/dynax-website
. ~/.dynax_env
PORT=6001 MY_URL="http://your-onion-address-here" python3 run_both.py > node.log 2>&1 &
sleep 10
curl -s localhost:6001/stats

## Step 7: Connect to the main network
curl --max-time 90 -X POST -H "Content-Type: application/json" -d '{"peer":"http://7elhinjau6eqcvbji4zitx2kb42njek5zitv6iwg6kkhup7qaclp5sqd.onion"}' localhost:6001/peers/add

This can take 60-90 seconds since it connects over Tor. Success looks like {"status":"added",...}.

## Step 8: Verify sync
Wait 1-2 minutes, then check:
curl -s localhost:6001/stats

If blocks climbs toward the main chain's current height, you're synced.

## Last step: tell the maintainer
Send your .onion address back so it can be added as a peer on the main node too -- this makes the connection two-way.

---

Testnet notice: DYX has no monetary value. Running a node means your phone does real background work (mining is locked by default, but sync and peer discovery run continuously) -- keep it charged and on stable Wi-Fi.
