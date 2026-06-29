from flask import Flask, send_file, jsonify, request
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

@app.route('/logo.png')
def logo():
    return send_file('logo.png', mimetype='image/png')

@app.route('/manifest.json')
def manifest():
    return send_file('manifest.json', mimetype='application/json')

@app.route('/sw.js')
def sw():
    return send_file('sw.js', mimetype='application/javascript')


NODE = 'https://web-production-8bbb8.up.railway.app'

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


def proxy(path, timeout=5):
    import requests
    try:
        r = requests.get(f"{NODE}{path}", timeout=timeout)
        return r.text, r.status_code, {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
    except:
        return "{}", 500, {"Content-Type": "application/json"}

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


@app.route('/testnet')
def testnet_info():
    return jsonify({
        "mode": "TESTNET",
        "warning": "This is a test network. Coins have no real value.",
        "chain_may_reset": True,
        "faucet": "https://dynax-website-2.onrender.com/faucet",
        "explorer": "https://dynax-website-2.onrender.com/explorer",
        "network_id": 1337,
        "symbol": "DYX"
    })

@app.route('/dashboard')
def dashboard():
    return send_file('dashboard.html')

@app.route('/start')
def start_page():
    return send_file('getting-started.html')

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

        sig = sk.sign(hashlib.sha3_256(msg.encode()).digest()).hex()

        r = requests.post(f'{NODE}/tx/send', json={
            "from": FAUCET_ADDRESS,
            "to": to_addr,
            "amount": amount,
            "fee": fee,
            "private_key": FAUCET_PRIVATE_KEY
        }, timeout=10)

        faucet_claims[to_addr] = now
        # Auto-mine เพื่อ confirm tx
        import time as _time
        _time.sleep(2)
        try:
            requests.get(f'{NODE}/mine/{FAUCET_ADDRESS}', timeout=60)
        except:
            pass
        return jsonify({"success": True, "amount": amount, "to": to_addr})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


def proxy(path, timeout=5):
    import requests
    try:
        r = requests.get(f"{NODE}{path}", timeout=timeout)
        return r.text, r.status_code, {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
    except:
        return "{}", 500, {"Content-Type": "application/json"}

@app.route("/api/node/stats")
def api_node_stats():
    return proxy("/stats")

@app.route("/api/node/peers")
def api_node_peers():
    return proxy("/peers")

@app.route("/api/node/blocks")
def api_node_blocks():
    return proxy("/blocks", timeout=10)

@app.route("/api/node/state")
def api_node_state():
    return proxy("/state", timeout=10)

@app.route("/api/node/pending")
def api_node_pending():
    return proxy("/pending")

@app.route("/api/node/snapshot/info")
def api_node_snapshot():
    return proxy("/snapshot/info")

@app.route("/api/node/info")
def api_node_info():
    return proxy("/api/v1/info")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
