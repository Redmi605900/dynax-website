import time
import json
import hashlib
import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

PORT = int(os.environ.get("PORT", 6001))

PEERS = [
    "http://127.0.0.1:6002",
    "http://127.0.0.1:6003"
]

CHAIN_FILE = f"chain_{PORT}.json"


# ─────────────────────────────
# BLOCK
# ─────────────────────────────
class Block:
    def __init__(self, index, prev_hash, data, timestamp=None, nonce=0):
        self.index = index
        self.prev_hash = prev_hash
        self.timestamp = timestamp or int(time.time())
        self.data = data
        self.nonce = nonce
        self.hash = self.calc_hash()

    def calc_hash(self):
        raw = f"{self.index}{self.prev_hash}{self.timestamp}{json.dumps(self.data, sort_keys=True)}{self.nonce}"
        return hashlib.sha3_256(raw.encode()).hexdigest()

    def to_dict(self):
        return self.__dict__


# ─────────────────────────────
# NODE
# ─────────────────────────────
class Node:
    def __init__(self):
        self.chain = []
        self.mempool = []
        self.load()

    def load(self):
        if not os.path.exists(CHAIN_FILE):
            self.chain = [Block(0, "0"*64, [])]
            self.save()
            return

        with open(CHAIN_FILE) as f:
            data = json.load(f)

        self.chain = [
            Block(b["index"], b["prev_hash"], b["data"], b["timestamp"], b["nonce"])
            for b in data
        ]

    def save(self):
        with open(CHAIN_FILE, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    # ─────────────────────────
    # VALIDATION
    # ─────────────────────────
    def valid_chain(self, chain):
        for i in range(1, len(chain)):
            c = chain[i]
            p = chain[i-1]

            if c.index != p.index + 1:
                return False
            if c.prev_hash != p.hash:
                return False

            raw = f"{c.index}{c.prev_hash}{c.timestamp}{json.dumps(c.data, sort_keys=True)}{c.nonce}"
            if c.hash != hashlib.sha3_256(raw.encode()).hexdigest():
                return False

        return True

    # ─────────────────────────
    # SYNC (MULTI NODE CORE)
    # ─────────────────────────
    def sync(self):
        longest = self.chain

        for peer in PEERS:
            try:
                r = requests.get(f"{peer}/chain")
                data = r.json()

                new_chain = [
                    Block(b["index"], b["prev_hash"], b["data"], b["timestamp"], b["nonce"])
                    for b in data
                ]

                if len(new_chain) > len(longest) and self.valid_chain(new_chain):
                    longest = new_chain

            except:
                pass

        if longest != self.chain:
            self.chain = longest
            self.save()
            return True

        return False

    # ─────────────────────────
    # MINE + BROADCAST
    # ─────────────────────────
    def mine(self, miner):
        reward = {
            "from": "SYSTEM",
            "to": miner,
            "amount": 50,
            "timestamp": int(time.time())
        }

        data = self.mempool + [reward]

        last = self.chain[-1]
        block = Block(len(self.chain), last.hash, data)

        while not block.hash.startswith("0000"):
            block.nonce += 1
            block.hash = block.calc_hash()

        self.chain.append(block)
        self.mempool = []
        self.save()

        # broadcast to peers
        for peer in PEERS:
            try:
                requests.post(f"{peer}/receive_block", json=block.to_dict())
            except:
                pass

        return block


node = Node()


# ─────────────────────────────
# API
# ─────────────────────────────
@app.route("/")
def home():
    return {
        "node": PORT,
        "blocks": len(node.chain)
    }


@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])


@app.route("/mine/<miner>")
def mine(miner):
    return jsonify(node.mine(miner).to_dict())


@app.route("/sync")
def sync():
    return {"synced": node.sync()}


@app.route("/receive_block", methods=["POST"])
def receive_block():
    data = request.json

    block = Block(
        data["index"],
        data["prev_hash"],
        data["data"],
        data["timestamp"],
        data["nonce"]
    )

    node.chain.append(block)
    node.save()

    return {"status": "received"}
if __name__ == "__main__":
    print("=== DYNAX NODE STARTING ===")
    app.run(host="0.0.0.0", port=PORT)
