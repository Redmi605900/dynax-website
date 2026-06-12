DYNAX (DYX) Mining Guide
Get free DYX by mining — No special hardware needed
What is DYNAX Mining?
DYNAX uses Proof-of-Work (PoW) — the same mechanism as Bitcoin. Your device competes to find a valid block hash and earns 50 DYX as reward.
No GPU required. Anyone can mine from a phone or laptop.
Requirements
Python 3.8+
Internet connection
Any device (Android, Linux, Windows, Mac)
Step 1: Install Dependencies
pip install flask ecdsa requests
Step 2: Download Node Software
 ืื  # Clone from GitHub
git clone https://github.com/Redmi605900/dynax-node2
cd dynax-node2
Or download dynax_node.py directly from:
github.com/Redmi605900/dynax-node2
Step 3: Create Your Wallet
Visit: dynax-website.vercel.app/wallet.html
Click NEW
Click GENERATE WALLET
Save your Private Key — cannot be recovered!
Copy your Address (starts with DX...)
Step 4: Run Your Node
python dynax_node.py
You should see:
=== DYNAX Node v2.5.0 ===
🌐 Running on http://0.0.0.0:6001
Step 5: Connect to Network
Add the main node as peer:
curl -X POST http://localhost:6001/peers/add \
  -H "Content-Type: application/json" \
  -d '{"peer": "https://dynax-node2.onrender.com"}'
Sync the chain:
curl -X POST http://localhost:6001/sync
Step 6: Start Mining
Replace YOUR_DX_ADDRESS with your wallet address:
curl http://localhost:6001/mine/YOUR_DX_ADDRESS
Example:
curl http://localhost:6001/mine/DXa5ae9ccc94279d4f52b4f4e694a5a3b2f4f5ece3
⛏️ Mining block #18...
✅ Block #18 mined! Reward: 50 DYX
Step 7: Check Your Balance
curl http://localhost:6001/balance/YOUR_DX_ADDRESS
Or visit Explorer:
dynax-website.vercel.app/explorer.html
Auto-Mine Script
Mine continuously:
while true; do
  curl -s http://localhost:6001/mine/YOUR_DX_ADDRESS > /dev/null
  echo "Mined! $(date)"
  sleep 1
done
Android (Termux) Setup
# Install Termux from F-Droid
pkg update
pkg install python git
pip install flask ecdsa requests
git clone https://github.com/Redmi605900/dynax-node2
cd dynax-node2
python dynax_node.py
Network Info
Parameter
Value
Block Reward
50 DYX
Block Time
~12 seconds
Difficulty
Auto-adjusts
Max Supply
11,000,000 DYX
Algorithm
SHA3-256 PoW
Links
Website: dynax-website.vercel.app
Explorer: dynax-website.vercel.app/explorer.html
Wallet: dynax-website.vercel.app/wallet.html
Whitepaper: dynax-website.vercel.app/whitepaper.md
Telegram: @QChainOfficial
Twitter: @QChainOfficial
DYNAX — Decentralized Layer 1 Blockchain
By Hideko Nanoura

