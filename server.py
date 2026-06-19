from flask import Flask, render_template, jsonify, redirect, send_from_directory
import requests
import os

app = Flask(__name__, 
    template_folder='templates',
    static_folder='assets',
    static_url_path='/assets'
)

# URLs ของ services (localtunnel)
SERVICES = {
    'node': 'https://dynax-node.loca.lt',
    'explorer': 'https://dynax-explorer.loca.lt',
    'mobile': 'https://dynax-mobile.loca.lt',
    'dex': 'https://dynax-dex.loca.lt',
    'dvm': 'https://dynax-dvm.loca.lt'
}

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/api/stats')
def api_stats():
    try:
        blocks_res = requests.get(SERVICES['node'] + '/blocks', timeout=5)
        blocks = blocks_res.json()
        total_txs = sum(len(b.get('transactions', [])) for b in blocks)
        
        try:
            dvm_res = requests.get(SERVICES['dvm'] + '/contracts', timeout=5)
            dvm_data = dvm_res.json()
            total_contracts = dvm_data.get('total', 0)
        except:
            total_contracts = 0
        
        return jsonify({
            'blocks': len(blocks),
            'transactions': total_txs,
            'contracts': total_contracts,
            'status': 'online'
        })
    except Exception as e:
        return jsonify({
            'blocks': 24,
            'transactions': 37,
            'contracts': 2,
            'status': 'offline',
            'error': str(e)
        })

# Redirect routes
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
    print(f"🚀 DYNAX Server running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
