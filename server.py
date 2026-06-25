from flask import Flask, send_file, jsonify
import os

app = Flask(__name__, static_folder='assets', static_url_path='/assets')

@app.route('/')
def home():
    return send_file('landing.html')

@app.route('/dex')
def dex_page():
    return send_file('dex.html')

@app.route('/explorer')
def explorer_page():
    return send_file('explorer.html')

@app.route('/wallet')
def wallet_page():
    return send_file('wallet.html')

@app.route('/whitepaper')
def whitepaper():
    return send_file('whitepaper.html')

@app.route('/api/stats')
def api_stats():
    try:
        import requests
        r = requests.get('https://dynax-node2.onrender.com/', timeout=5)
        data = r.json()
        return jsonify({
            'blocks': data.get('blocks', 0),
            'transactions': 0,
            'nodes': 1,
            'difficulty': 4,
            'symbol': 'DYX',
            'reward': 50,
            'status': 'online'
        })
    except:
        return jsonify({'blocks': 0, 'transactions': 0, 'nodes': 1, 'status': 'online'})

@app.route('/manifest.json')
def manifest():
    return send_file('manifest.json', mimetype='application/json')

@app.route('/sw.js')
def sw():
    return send_file('sw.js', mimetype='application/javascript')


NODE = 'https://dynax-node2.onrender.com'

@app.route('/balance/<addr>')
def proxy_balance(addr):
    import requests
    r = requests.get(f'{NODE}/balance/{addr}', timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}

@app.route('/tx', methods=['POST'])
def proxy_tx():
    import requests
    r = requests.post(f'{NODE}/tx', json=request.json, timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}

@app.route('/txs/<addr>')
def proxy_txs(addr):
    import requests
    r = requests.get(f'{NODE}/txs/{addr}', timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}

@app.route('/tx/send', methods=['POST'])
def proxy_tx_send():
    import requests
    r = requests.post(f'{NODE}/tx/send', json=request.json, timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}


@app.route('/dex/pool')
def proxy_dex_pool():
    import requests
    r = requests.get(f'{NODE}/dex/pool', timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}

@app.route('/dex/swap', methods=['POST'])
def proxy_dex_swap():
    import requests
    r = requests.post(f'{NODE}/dex/swap', json=request.json, timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}

@app.route('/dex/liquidity', methods=['POST'])
def proxy_dex_liquidity():
    import requests
    r = requests.post(f'{NODE}/dex/liquidity', json=request.json, timeout=5)
    return r.text, r.status_code, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

import time
import json
import hashlib

# Faucet config
FAUCET_ADDRESS = "DX540b35d9c3b3d653904c70553e9fba2ce830e84dc02aad1dcff766710f7ecf55"
FAUCET_PRIVATE_KEY = os.environ.get("FAUCET_PRIVATE_KEY", "")
FAUCET_AMOUNT = 10
FAUCET_COOLDOWN = 43200  # 12 ชั่วโมง
faucet_claims = {}  # {address: timestamp}

@app.route('/faucet')
def faucet_page():
    return send_file('faucet.html')

@app.route('/api/faucet', methods=['POST'])
def api_faucet():
    import requests
    from ecdsa import SigningKey, SECP256k1

    data = request.json
    to_addr = data.get('address', '').strip()

    if not to_addr or not to_addr.startswith('DX'):
        return jsonify({"error": "Invalid address"}), 400

    # เช็ค cooldown
    now = time.time()
    if to_addr in faucet_claims:
        elapsed = now - faucet_claims[to_addr]
        if elapsed < FAUCET_COOLDOWN:
            remaining = int((FAUCET_COOLDOWN - elapsed) / 3600)
            mins = int((FAUCET_COOLDOWN - elapsed) % 3600 / 60)
            return jsonify({"error": f"Please wait {remaining}h {mins}m before claiming again"}), 429

    if not FAUCET_PRIVATE_KEY:
        return jsonify({"error": "Faucet not configured"}), 500

    try:
        sk = SigningKey.from_string(bytes.fromhex(FAUCET_PRIVATE_KEY), curve=SECP256k1)
        amount = FAUCET_AMOUNT
        fee = 0.01
        msg = json.dumps({"amount": amount, "fee": fee, "from": FAUCET_ADDRESS, "to": to_addr}, sort_keys=True)
cat > faucet.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DYNAX Faucet</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0a0a; color: #fff; font-family: 'Courier New', monospace; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .container { max-width: 500px; width: 90%; }
  h1 { color: #d4af37; font-size: 2rem; text-align: center; margin-bottom: 0.5rem; }
  .subtitle { color: #888; text-align: center; margin-bottom: 2rem; }
  .box { background: #111; border: 1px solid #d4af37; border-radius: 12px; padding: 2rem; }
  .info { display: flex; justify-content: space-between; margin-bottom: 1.5rem; }
  .info-item { text-align: center; }
  .info-item .value { color: #d4af37; font-size: 1.5rem; font-weight: bold; }
  .info-item .label { color: #888; font-size: 0.8rem; margin-top: 0.3rem; }
  input { width: 100%; padding: 0.8rem; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #fff; font-family: monospace; font-size: 0.85rem; margin-bottom: 1rem; }
  input:focus { outline: none; border-color: #d4af37; }
  button { width: 100%; padding: 1rem; background: #d4af37; color: #000; border: none; border-radius: 8px; font-size: 1rem; font-weight: bold; cursor: pointer; }
  button:hover { background: #f0c040; }
  button:disabled { background: #555; cursor: not-allowed; }
  .result { margin-top: 1rem; padding: 1rem; border-radius: 8px; text-align: center; display: none; }
  .result.success { background: #0a2a0a; border: 1px solid #2a7a2a; color: #4caf50; }
  .result.error { background: #2a0a0a; border: 1px solid #7a2a2a; color: #f44336; }
  .nav { text-align: center; margin-top: 1.5rem; }
  .nav a { color: #d4af37; text-decoration: none; margin: 0 1rem; }
  .footer { margin-top: 2rem; text-align: center; color: #444; font-size: 0.8rem; }
</style>
</head>
<body>
<div class="container">
  <h1>💧 DYNAX Faucet</h1>
  <p class="subtitle">Get free DYX to get started</p>
  <div class="box">
    <div class="info">
      <div class="info-item">
        <div class="value">10 DYX</div>
        <div class="label">Per Claim</div>
      </div>
      <div class="info-item">
        <div class="value">12h</div>
        <div class="label">Cooldown</div>
      </div>
      <div class="info-item">
        <div class="value">FREE</div>
        <div class="label">No Registration</div>
      </div>
    </div>
    <input type="text" id="address" placeholder="Enter your DX... wallet address" />
    <button id="claimBtn" onclick="claim()">💧 Claim 10 DYX</button>
    <div class="result" id="result"></div>
  </div>
  <div class="nav">
    <a href="/">Home</a>
    <a href="/wallet">Wallet</a>
    <a href="/explorer">Explorer</a>
  </div>
  <div class="footer">
    <p>Decentralized • No KYC • Trustless</p>
  </div>
</div>
<script>
async function claim() {
  const addr = document.getElementById('address').value.trim();
  const btn = document.getElementById('claimBtn');
  const result = document.getElementById('result');

  if (!addr.startsWith('DX')) {
    showResult('error', 'Please enter a valid DX... address');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Processing...';

  try {
    const r = await fetch('/api/faucet', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({address: addr})
    });
    const data = await r.json();

    if (data.success) {
      showResult('success', `✅ Successfully sent 10 DYX to ${addr.slice(0,12)}...`);
    } else {
      showResult('error', '❌ ' + (data.error || 'Something went wrong'));
    }
  } catch(e) {
    showResult('error', '❌ Network error, please try again');
  }

  btn.disabled = false;
  btn.textContent = '💧 Claim 10 DYX';
}

function showResult(type, msg) {
  const el = document.getElementById('result');
  el.className = 'result ' + type;
  el.textContent = msg;
  el.style.display = 'block';
}
</script>
</body>
</html>
