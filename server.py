from flask import Flask, send_file, jsonify, redirect, request
import os

app = Flask(__name__, static_folder='assets', static_url_path='/assets')

BASE_URL = "http://172.17.78.115"

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
