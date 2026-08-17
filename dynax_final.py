from flask import Flask, send_file, jsonify
import dynax_node_v20

app = Flask(__name__)

# ✅ หน้าเว็บมาก่อนทุกอย่าง — จะได้ไม่โดนทับ
@app.route('/')
def show_home():
    return send_file('index.html')

@app.route('/dashboard')
def show_dash():
    return send_file('dashboard.html')

# ✅ API มาทีหลัง
@app.route('/api')
def show_api():
    return jsonify({
        "api_v1": True,
        "blocks": 12,
        "network": "DYNAX v20 Secure"
    })

# ✅ ดึงฟังก์ชันระบบหลักมาใช้ครบถ้วน
import dynax_node_v20 as core
core.app = app

# ✅ เริ่มทำงานที่พอร์ต 6002 แน่นอน
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6002, debug=False, use_reloader=False)
