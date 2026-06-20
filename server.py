from flask import Flask, send_file, jsonify, redirect, request
import os
import requests

app = Flask(__name__, static_folder='assets', static_url_path='/assets')

# ใช้ localtunnel Node
NODE_URL = "http://172.17.78.115:6002"

@app.route('/')
def home():
    return send_file('landing.html')

@app.route('/api/stats')
def api_stats():
    return jsonify({
        'blocks': 24,
        'transactions': 37,
        'contracts': 2,
        'status': 'online'
    })

@app.route('/explorer')
def explorer_page():
    return send_file('explorer.html')

@app.route('/wallet')
def wallet_page():
    return send_file('wallet.html')

@app.route('/dex')
def dex_page():
    return send_file('dex.html')

@app.route('/dvm')
def dvm_page():
    return send_file('explorer.html')

@app.route('/whitepaper')
def whitepaper():
    return send_file('whitepaper.html')

@app.route('/manifest.json')
def manifest():
    return send_file('manifest.json', mimetype='application/json')
@app.route('/sw.js')
def sw():
    return send_file('sw.js', mimetype='application/javascript')

# Proxy routes สำหรับ DEX
@app.route('/balance/<addr>')
def proxy_balance(addr):
    try:
        r = requests.get(f"{NODE_URL}/balance/{addr}", timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 503

@app.route('/send', methods=['POST'])
def proxy_send():
    try:
        r = requests.post(f"{NODE_URL}/send", json=request.json, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 503

@app.route('/chain')
def proxy_chain():
    try:
        r = requests.get(f"{NODE_URL}/chain", timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 503

@app.route('/mine/<addr>')
def proxy_mine(addr):
    try:
        r = requests.get(f"{NODE_URL}/mine/{addr}", timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 503

@app.route('/blocks')
def proxy_blocks():
    try:
        r = requests.get(f"{NODE_URL}/blocks", timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 503

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
