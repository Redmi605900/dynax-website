from flask import send_file, jsonify
import dynax_node_v20

app = dynax_node_v20.app

def dashboard_home():
    return send_file('landing.html')
app.view_functions['home'] = dashboard_home

@app.route('/start')
def dashboard_start():
    return send_file('getting-started.html')

@app.route('/faucet')
def dashboard_faucet():
    return send_file('faucet.html')

@app.route('/api')
def dashboard_api_info():
    return jsonify({"api_v1":True,"blocks":12,"network":"DYNAX v20 Secure"})

@app.route('/dashboard')
def dashboard_show():
    return send_file('dashboard.html')

@app.route('/elliptic.min.js')
def serve_elliptic():
    return send_file('elliptic.min.js', mimetype='application/javascript')

@app.route('/sha3.min.js')
def serve_sha3():
    return send_file('sha3.min.js', mimetype='application/javascript')

@app.route('/qrcode.min.js')
def serve_qrcode():
    return send_file('qrcode.min.js', mimetype='application/javascript')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6001)
