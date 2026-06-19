
import time
import json
import hashlib
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

CHAIN_FILE = os.path.expanduser("~/qchain-website/dynax_chain.json")


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
# NODE CORE
# ─────────────────────────────
class Node:
    def __init__(self):
        self.chain = []
        self.mempool = []
        self.load_chain()

    # ─────────────────────────
    # LOAD + FIX CORRUPTION
    # ─────────────────────────
    def load_chain(self):
        if not os.path.exists(CHAIN_FILE):
            self.chain = [Block(0, "0"*64, [])]
            self.save()
            return

        try:
            with open(CHAIN_FILE) as f:
                data = json.load(f)

            chain = []
            for b in data:
                block = Block(
                    b.get("index", 0),
                    b.get("prev_hash", "0"*64),
                    b.get("data", []),
                    b.get("timestamp", int(time.time())),
                    b.get("nonce", 0)
                )
                chain.append(block)

            # validate BEFORE accept
            if self.validate_chain(chain):
                self.chain = chain
            else:
                print("⚠️ Chain corrupted → fallback genesis")
                self.chain = [Block(0, "0"*64, [])]

        except:
            self.chain = [Block(0, "0"*64, [])]

    # ─────────────────────────
    # SAVE (ATOMIC STYLE)
    # ─────────────────────────
    def save(self):
        tmp = CHAIN_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

        os.replace(tmp, CHAIN_FILE)

    # ─────────────────────────
    # CHAIN VALIDATION (ANTI FORK)
    # ─────────────────────────
    def validate_chain(self, chain):
        for i in range(1, len(chain)):
            curr = chain[i]
            prev = chain[i - 1]

            # 1. index must follow
            if curr.index != prev.index + 1:
                return False

            # 2. link must match
            if curr.prev_hash != prev.hash:
                return False

            # 3. hash must be valid
            raw = f"{curr.index}{curr.prev_hash}{curr.timestamp}{json.dumps(curr.data, sort_keys=True)}{curr.nonce}"
            if curr.hash != hashlib.sha3_256(raw.encode()).hexdigest():
                return False

        return True

    # ─────────────────────────
    # GET BALANCE
    # ─────────────────────────
    def balance(self, addr):
        bal = 0
        for b in self.chain:
            for tx in b.data:
                if tx.get("to") == addr:
                    bal += tx.get("amount", 0)
                if tx.get("from") == addr:
                    bal -= tx.get("amount", 0)
        return bal

    # ─────────────────────────
    # ADD BLOCK (LOCKED)
    # ─────────────────────────
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

        # PoW
        while not block.hash.startswith("0000"):
            block.nonce += 1
            block.hash = block.calc_hash()

        # 🔐 LOCK CHECK (ANTI FORK)
        if block.prev_hash != self.chain[-1].hash:
            return {"error": "fork detected"}

        self.chain.append(block)
        self.mempool = []
        self.save()

        return block


node = Node()


# ─────────────────────────────
# API
# ─────────────────────────────
@app.route("/")
def home():
    return {
        "status": "DYNAX LOCK SYSTEM ACTIVE",
        "blocks": len(node.chain)
    }


@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])


@app.route("/balance/<addr>")
def balance(addr):
    return {"address": addr, "balance": node.balance(addr)}


@app.route("/mine/<miner>")
def mine(miner):
    return jsonify(node.mine(miner))


if __name__ == "__main__":
    print("=== DYNAX LOCK SYSTEM STARTED ===")
    app.run(host="0.0.0.0", port=6001)
