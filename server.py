from flask import Flask, send_file, jsonify, redirect
import os

app = Flask(__name__, static_folder='assets', static_url_path='/assets')

# URLs ของ services (localtunnel)
SERVICES = {
    'explorer': 'https://dynax-explorer.loca.lt',
    'mobile': 'https://dynax-mobile.loca.lt',
    'dex': 'https://dynax-dex.loca.lt',
    'dvm': 'https://dynax-dvm.loca.lt'
}

@app.route('/')
def home():
    return send_file('landing.html')

@app.route('/api/stats')
def api_stats():
    # ใช้ค่า hardcoded จาก Block Explorer ที่เห็น
    return jsonify({
        'blocks': 24,
        'transactions': 37,
        'contracts': 2,
        'status': 'online'
    })

# Redirect routes ไปยัง localtunnel services
@app.route('/explorer')
def explorer():
    return redirect(SERVICES['explorer'])

@app.route('/wallet')
def wallet():
    return redirect(SERVICES['mobile'])

@app.route('/dex')
def dex():
    return redirect(SERVICES['dex'])

@app.route('/dvm')
def dvm():
    return redirect(SERVICES['dvm'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f" DYNAX Server running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
