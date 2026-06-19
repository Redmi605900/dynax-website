from flask import Flask, send_file, jsonify, request
import requests

app = Flask(__name__)
DVM_URL = "http://127.0.0.1:6005"
NODE_URL = "http://127.0.0.1:6002"

@app.route("/")
def home():
    return send_file("explorer.html")

@app.route("/api/contracts")
def api_contracts():
    try:
        r = requests.get(DVM_URL + "/contracts", timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "contracts": [], "total": 0})

@app.route("/api/stats")
def api_stats():
    try:
        blocks = requests.get(NODE_URL + "/blocks", timeout=3).json()
        contracts = requests.get(DVM_URL + "/contracts", timeout=3).json()
        total_txs = sum(len(b.get("transactions", [])) for b in blocks)
        return jsonify({
            "total_blocks": len(blocks),
            "total_transactions": total_txs,
            "total_contracts": contracts.get("total", 0),
            "status": "online"
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    print("=" * 50)
    print("DYNAX Block Explorer v1.0")
    print("=" * 50)
    print("Open: http://127.0.0.1:6006")
    print("=" * 50)
    app.run(host="0.0.0.0", port=6006, debug=False)
