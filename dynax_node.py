from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# โหลด chain จากไฟล์ dynax_chain.json
CHAIN_FILE = "dynax_chain.json"

def load_chain():
    if os.path.exists(CHAIN_FILE):
        with open(CHAIN_FILE, "r") as f:
            return json.load(f)
    else:
        return {"chain": []}

def save_chain(chain_data):
    with open(CHAIN_FILE, "w") as f:
        json.dump(chain_data, f, indent=4)

# -------------------------------
# Endpoint: ดู chain ทั้งหมด
# -------------------------------
@app.route("/chain", methods=["GET"])
def get_chain():
    chain = load_chain()
    return jsonify(chain)

# -------------------------------
# Endpoint: ขุด block ใหม่
# -------------------------------
@app.route("/mine/<address>", methods=["GET"])
def mine_block(address):
    chain = load_chain()
    new_block = {
        "index": len(chain["chain"]) + 1,
        "miner": address,
        "reward": 50
    }
    chain["chain"].append(new_block)
    save_chain(chain)
    return jsonify({"message": "Block mined successfully", "block": new_block})

# -------------------------------
# Endpoint: อัปโหลด chain จาก local
# -------------------------------
@app.route("/upload-chain", methods=["POST"])
def upload_chain():
    try:
        chain_data = request.get_json()

        if not chain_data:
            return jsonify({"error": "No chain data received"}), 400

        save_chain(chain_data)

        return jsonify({"message": "Chain uploaded successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# -------------------------------
# Run server
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6002)
