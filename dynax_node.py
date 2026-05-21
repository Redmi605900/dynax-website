import time
import json
import hashlib
import os
import hmac
import socket
import threading
from flask import Flask, request, jsonify

CHAIN_FILE = "/data/data/com.termux/files/home/dynax_chain.json"
DIFFICULTY = 4
BLOCK_REWARD = 50
SECRET_KEY = "DYNAX_SECRET_v1"
PORT = 6001

class Block:
    def __init__(self, index, prev_hash, txs, nonce=0):
        self.index = index
        self.timestamp = int(time.time())
        self.prev_hash = prev_hash
        self.transactions = txs
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "transactions": self.transactions,
            "nonce": self.nonce
        }, sort_keys=True)
        return hashlib.sha3_256(data.encode()).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "transactions": self.transactions,
            "nonce": self.nonce,
            "hash": self.hash,
            "tx_count": len(self.transactions)
        }

class DYNAXNode:
    def __init__(self):
        self.chain = []
        self.mempool = []
        self.peers = []
        self.load_chain()

    def save_chain(self):
        with open(CHAIN_FILE, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def load_chain(self):
        if not os.path.exists(CHAIN_FILE):
            genesis_txs = [
                {"from": "GENESIS", "to": "DX5293ada2aa014167fa15942c4318b6235fe7d1", "amount": 300000},
                {"from": "GENESIS", "to": "DXf2a9fc9e0b20602d66af8ecae2032f0e56c20f", "amount": 7000},
                {"from": "GENESIS", "to": "DX8a6e18a35d23368fa553f87552693d91f58ce6", "amount": 445},
                {"from": "GENESIS", "to": "DX9ac31f667d87ec3a5940ac409d9a54de8b0507", "amount": 137}
            ]
            genesis = Block(0, "0"*64, genesis_txs)
            self.chain.append(genesis)
            self.save_chain()
            return
        with open(CHAIN_FILE) as f:
            data = json.load(f)
        for item in data:
            b = Block(item["index"], item["prev_hash"], item["transactions"], item["nonce"])
            b.timestamp = item["timestamp"]
            b.hash = item["hash"]
            self.chain.append(b)

    def last_block(self):
        return self.chain[-1]

    def verify_chain(self):
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i-1]
            if curr.prev_hash != prev.hash:
                return False
            if curr.hash != curr.calculate_hash():
                return False
        return True

    def get_balance(self, address):
        balance = 0
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("from") == address:
                    balance -= tx["amount"]
                if tx.get("to") == address:
                    balance += tx["amount"]
        return balance

    def add_transaction(self, tx):
        required = ["from", "to", "amount", "signature"]
        for r in required:
            if r not in tx:
                return {"success": False, "error": f"missing {r}"}
        if tx["amount"] <= 0:
            return {"success": False, "error": "invalid amount"}
        balance = self.get_balance(tx["from"])
        if balance < tx["amount"] and tx["from"] != "GENESIS":
            return {"success": False, "error": f"insufficient balance: {balance}"}
        tx_canonical = {"from": tx["from"], "to": tx["to"], "amount": tx["amount"]}
        message = json.dumps(tx_canonical, sort_keys=True).encode()
        expected_sig = hmac.new(SECRET_KEY.encode(), message, hashlib.sha3_256).hexdigest()
        if expected_sig != tx["signature"]:
            return {"success": False, "error": "invalid signature"}
        tx["txid"] = hashlib.sha3_256(json.dumps(tx_canonical, sort_keys=True).encode()).hexdigest()
        tx["timestamp"] = int(time.time())
        self.mempool.append(tx)
        return {"success": True, "txid": tx["txid"]}

    def mine(self, miner_address):
        reward_tx = {
            "from": "NETWORK",
            "to": miner_address,
            "amount": BLOCK_REWARD,
            "txid": hashlib.sha3_256(f"reward_{len(self.chain)}".encode()).hexdigest()
        }
        txs = [reward_tx] + self.mempool
        block = Block(len(self.chain), self.last_block().hash, txs)
        print(f"⛏️ Mining block #{block.index}...")
        while not block.hash.startswith("0" * DIFFICULTY):
            block.nonce += 1
            block.hash = block.calculate_hash()
        self.chain.append(block)
        self.mempool = []
        self.save_chain()
        print(f"✅ Block #{block.index} mined: {block.hash[:20]}...")
        return block

    def get_tx(self, txid):
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("txid") == txid:
                    return {"tx": tx, "block": block.index}
        return None

    def info(self):
        return {
            "name": "DYNAX",
            "symbol": "DYX",
            "version": "1.0.0",
            "blocks": len(self.chain),
            "mempool": len(self.mempool),
            "peers": len(self.peers),
            "difficulty": DIFFICULTY,
            "reward": BLOCK_REWARD,
            "max_supply": 11000000,
            "valid": self.verify_chain()
        }

# Flask API
app = Flask(__name__)
node = DYNAXNode()

@app.route("/")
def index():
    return jsonify(node.info())

@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])

@app.route("/block/<int:index>")
def get_block(index):
    if index < len(node.chain):
        return jsonify(node.chain[index].to_dict())
    return jsonify({"error": "block not found"}), 404

@app.route("/tx/<txid>")
def get_tx(txid):
    result = node.get_tx(txid)
    if result:
        return jsonify(result)
    return jsonify({"error": "tx not found"}), 404

@app.route("/balance/<address>")
def balance(address):
    return jsonify({
        "address": address,
        "balance": node.get_balance(address),
        "symbol": "DYX"
    })

@app.route("/mempool")
def mempool():
    return jsonify({"mempool": node.mempool, "count": len(node.mempool)})

@app.route("/send", methods=["POST"])
def send():
    tx = request.get_json()
    result = node.add_transaction(tx)
    return jsonify(result)

@app.route("/mine/<address>")
def mine(address):
    block = node.mine(address)
    return jsonify({"success": True, "block": block.to_dict()})

@app.route("/peers")
def peers():
    return jsonify({"peers": node.peers})

if __name__ == "__main__":
    print("=== DYNAX Node v1.0.0 ===")
    print(json.dumps(node.info(), indent=2))
    print(f"\n🌐 API running on http://0.0.0.0:{PORT}")
    print("Endpoints:")
    print("  GET  /")
    print("  GET  /chain")
    print("  GET  /block/<index>")
    print("  GET  /tx/<txid>")
    print("  GET  /balance/<address>")
    print("  GET  /mempool")
    print("  GET  /mine/<address>")
    print("  POST /send")
    app.run(host="0.0.0.0", port=PORT, debug=False)
