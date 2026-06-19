from flask import Flask, send_file, jsonify, redirect
import os

app = Flask(__name__, static_folder='assets', static_url_path='/assets')

# IP จริงของเครื่อง
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

# Serve HTML pages directly
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
    # ถ้าไม่มี dvm.html ให้ใช้ explorer.html แทน หรือสร้างหน้าใหม่
    return send_file('explorer.html')

# API endpoints สำหรับ services (ถ้าต้องการ)
@app.route('/api/explorer')
def explorer_api():
    return redirect(f"{BASE_URL}:6006")

@app.route('/api/wallet')
def wallet_api():
    return redirect(f"{BASE_URL}:6007")

@app.route('/api/dex')
def dex_api():
    return redirect(f"{BASE_URL}:6004")

@app.route('/api/dvm')
def dvm_api():
    return redirect(f"{BASE_URL}:6005")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
