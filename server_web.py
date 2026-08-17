from flask import Flask, send_file, jsonify
import dynax_node_v20

app = dynax_node_v20.app

# เปลี่ยนหน้าหลักเป็นหน้าเว็บ
@app.route('/')
def home():
    return send_file('index.html')

# เก็บ API ไว้ใช้งาน
@app.route('/api')
def api_root():
    return jsonify({
        "api_v1": True,
        "blocks": 12,
        "network": "DYNAX v20 Secure"
    })

@app.route('/dashboard')
def dashboard():
    return send_file('dashboard.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6002)
