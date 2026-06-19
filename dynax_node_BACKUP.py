import time
import json
import hashlib
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

CHAIN_FILE = os.path.expanduser("~/qchain-website/dynax_chain.json")

WALLET_DIRS = [
    os.path.expanduser("~/qchain-website"),
    os.path.expanduser("~/wallets"),
    os.path.expanduser("~/DYNAX_GENESIS_BACKUP"),
]


# ─────────────────────────────
# BLOCK
# ─────────────────────────────
class Block:
    def __init__(self, index, prev_hash, data, timestamp=None, nonce=0):
        self.index = index
        self.prev_hash = prev_hash
        self.timestamp = timestamp or int(time.time())
        self.data = data  # transactions
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
        self.wallets = []
        self.load_chain()
        self.load_wallets()

    # ───────── WALLET SYSTEM ─────────
    def load_wallets(self):
        unique = {}

        for d in WALLET_DIRS:
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.startswith("wallet") and f.endswith(".json"):
                        path = os.path.join(d, f)

                        try:
                            with open(path) as wf:
                                w = json.load(wf)

                                addr = w.get("address")
                                if addr:
                                    if addr in unique:
                                        if w.get("timestamp", 0) > unique[addr].get("timestamp", 0):
                                            unique[addr] = w
                                    else:
                                        unique[addr] = w
                        except:
                            pass

        self.wallets = list(unique.values())

    # ───────── BALANCE ─────────
    def get_balance(self, address):
        balance = 0

        for block in self.chain:
            for tx in block.data:
                if tx["from"] == address:
                    balance -= tx["amount"]
                if tx["to"] == address:
                    balance += tx["amount"]

        return balance

    # ───────── VALIDATE CHAIN ─────────
    def validate(self, chain):
        for i in range(1, len(chain)):
            c = chain[i]
            p = chain[i - 1]

            if c.index != p.index + 1:
                return False

            if c.prev_hash != p.hash:
                return False

            raw = f"{c.index}{c.prev_hash}{c.timestamp}{json.dumps(c.data, sort_keys=True)}{c.nonce}"
            if c.hash != hashlib.sha3_256(raw.encode()).hexdigest():
                return False

        return True

    # ───────── LOAD CHAIN ─────────
    def load_chain(self):
        if not os.path.exists(CHAIN_FILE):
            genesis = Block(0, "0"*64, [])
            self.chain = [genesis]
            self.save()
            return

        try:
            with open(CHAIN_FILE) as f:
                data = json.load(f)

            self.chain = [
                Block(
                    b["index"],
                    b["prev_hash"],
                    b["data"],
                    b["timestamp"],
                    b["nonce"]
                )
                for b in data
            ]

        except:
            self.chain = [Block(0, "0"*64, [])]

    # ───────── SAVE ─────────
    def save(self):
        with open(CHAIN_FILE, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    # ───────── TX ─────────
    def create_tx(self, sender, receiver, amount):
        if sender != "SYSTEM":
            if self.get_balance(sender) < amount:
                return None

        return {
            "from": sender,
            "to": receiver,
            "amount": amount,
            "timestamp": int(time.time())
        }

    # ───────── MINING ─────────
    def mine(self, miner):
        reward = self.create_tx("SYSTEM", miner, 50)

        txs = self.mempool + [reward]

        last = self.chain[-1]
        block = Block(len(self.chain), last.hash, txs)

        while not block.hash.startswith("0000"):
            block.nonce += 1
            block.hash = block.calc_hash()

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
        "status": "DYNAX FULL RESTORE SYSTEM",
        "blocks": len(node.chain),
        "wallets": len(node.wallets)
    }


@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])


@app.route("/wallets")
def wallets():
    return jsonify(node.wallets)


@app.route("/balance/<addr>")
def balance(addr):
    return {
        "address": addr,
        "balance": node.get_balance(addr)
    }


@app.route("/tx", methods=["POST"])
def tx():
    data = request.json

    tx = node.create_tx(
        data["from"],
        data["to"],
        data["amount"]
    )

    if not tx:
        return {"error": "insufficient balance"}, 400

    node.mempool.append(tx)
    return {"status": "queued", "tx": tx}


@app.route("/mine/<miner>")
def mine(miner):
    block = node.mine(miner)
    return jsonify(block.to_dict())


# ─────────────────────────────
# RUN
# ─────────────────────────────
if __name__ == "__main__":
    print("=== DYNAX FULL RESTORE SYSTEM STARTED ===")
    app.run(host="0.0.0.0", port=6001)
