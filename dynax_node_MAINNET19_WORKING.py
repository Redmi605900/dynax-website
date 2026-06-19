

import time
import json
import hashlib
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

PORT = int(os.environ.get("PORT", 6001))

CHAIN_FILE = os.path.expanduser(
    f"~/qchain-website/dynax_chain_{PORT}.json"
)

PEERS = [
    "http://127.0.0.1:6001",
    "http://127.0.0.1:6002",
    "http://127.0.0.1:6003"
]

def validate_chain(chain):

    if len(chain) == 0:
        return False

    for i in range(1, len(chain)):

        prev = chain[i-1]
        curr = chain[i]

        if curr["index"] != prev["index"] + 1:
            return False

        if curr["prev_hash"] != prev["hash"]:
            return False

    return True

# -------------------------
# BLOCK
# -------------------------
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
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self):
        return self.__dict__


# -------------------------
# NODE CORE
# -------------------------
class Node:
    def __init__(self):
        self.chain = []
        self.mempool = []
        self.load_chain()

    def load_chain(self):
        if not os.path.exists(CHAIN_FILE):
            self.chain = [Block(0, "0"*64, [])]
            self.save()
            return

        try:
            with open(CHAIN_FILE) as f:
                data = json.load(f)

            if not validate_chain(data):
                raise Exception("CHAIN CORRUPTED")

            self.chain = []

            for b in data:
                block = Block(
                    b["index"],
                    b["prev_hash"],
                    b["data"],
                    b["timestamp"],
                    b["nonce"]
                )
                block.hash = b["hash"]
                self.chain.append(block)

        except:
            self.chain = [Block(0, "0"*64, [])]

    def save(self):
        tmp = CHAIN_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)
        os.replace(tmp, CHAIN_FILE)

    def balance(self, addr):
        bal = 0
        for b in self.chain:
            for tx in b.data:
                if tx.get("to") == addr:
                    bal += tx.get("amount", 0)
                if tx.get("from") == addr:
                    bal -= tx.get("amount", 0)
        return bal

    def send(self, sender, receiver, amount):
        amount = int(amount)

        if amount <= 0:
            return {"error": "invalid amount"}

        if self.balance(sender) < amount:
            return {"error": "insufficient balance"}

        tx = {
            "from": sender,
            "to": receiver,
            "amount": amount,
            "timestamp": int(time.time())
        }

        self.mempool.append(tx)
        return {"status": "queued", "tx": tx}

    def mine(self, miner):
        reward = {
            "from": "SYSTEM",
            "to": miner,
            "amount": 50,
            "timestamp": int(time.time())
        }

        txs = self.mempool + [reward]

        last = self.chain[-1]
        block = Block(len(self.chain), last.hash, txs)

        # Proof of Work
        while not block.hash.startswith("0000"):
            block.nonce += 1
            block.hash = block.calc_hash()

        self.chain.append(block)
        self.mempool = []
        self.save()

        return block


node = Node()


# -------------------------
# API
# -------------------------
@app.route("/")
def home():
    return {
        "status": "DYNAX CLEAN NODE ACTIVE",
        "blocks": len(node.chain)
    }


@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])


@app.route("/balance/<addr>")
def balance(addr):
    return {"address": addr, "balance": node.balance(addr)}


@app.route("/send/<sender>/<receiver>/<amount>")
def send(sender, receiver, amount):
    return jsonify(node.send(sender, receiver, amount))


@app.route("/mine/<miner>")
def mine(miner):
    b = node.mine(miner)
    return jsonify(b.to_dict())


# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    print(f"=== DYNAX CLEAN NODE STARTED ON {PORT} ===")
    app.run(host="0.0.0.0", port=PORT, debug=False)
