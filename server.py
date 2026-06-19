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

@app.route('/explorer')
def explorer():
    return redirect(f"{BASE_URL}:6006")

@app.route('/wallet')
def wallet():
    return redirect(f"{BASE_URL}:6007")

@app.route('/dex')
def dex():
    return redirect(f"{BASE_URL}:6004")

@app.route('/dvm')
def dvm():
    return redirect(f"{BASE_URL}:6005")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
