from flask import Flask, send_file, jsonify, request
import threading, time, json, hashlib, random, requests
from uuid import uuid4

# === เริ่มโค้ดระบบหลักเหมือนเดิม ===
app = Flask(__name__)

# โหลดข้อมูลบล็อกและเพียร์
try:
    with open("dynax_chain.json", "r") as f:
        blockchain = json.load(f)
except:
    blockchain = []

try:
    with open("peers.json", "r") as f:
        peers = json.load(f)
except:
    peers = []

# === เส้นทางหน้าเว็บ — ต้องมาก่อนเส้นทางอื่น! ===
@app.route('/')
def page_home():
    return send_file('index.html')

@app.route('/dashboard')
def page_dash():
    return send_file('dashboard.html')

@app.route('/explorer')
def page_explorer():
    return send_file('explorer.html')

@app.route('/wallet')
def page_wallet():
    return send_file('wallet.html')

# === เส้นทาง API — มาหลังหน้าเว็บ ===
@app.route('/api')
def api_info():
    return jsonify({
        "api_v1": True,
        "blocks": len(blockchain),
        "network": "DYNAX v20 Secure",
        "peers": len(peers)
    })

@app.route('/api/blocks')
def api_blocks():
    return jsonify(blockchain)

# === ฟังก์ชันอื่นๆ เหมือนในโค้ดเดิม ===
def auto_connect_peers():
    while True:
        time.sleep(5)

def auto_mining():
    while True:
        time.sleep(10)

# === เริ่มระบบ ===
if __name__ == '__main__':
    # เริ่มเธรดเบื้องหลัง
    threading.Thread(target=auto_connect_peers, daemon=True).start()
    threading.Thread(target=auto_mining, daemon=True).start()
    # รันเซิร์ฟเวอร์
    app.run(host='0.0.0.0', port=6002, debug=False, use_reloader=False)
