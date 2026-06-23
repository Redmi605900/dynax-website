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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
