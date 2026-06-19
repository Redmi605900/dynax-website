import time
import json
import hashlib
import os
from flask import Flask, jsonify, request
from ecdsa import SigningKey, SECP256k1, VerifyingKey, BadSignatureError

app = Flask(__name__)

CHAIN_FILE = os.path.expanduser("~/qchain-website/dynax_chain.json")


# ─────────────────────────────
# WALLET (BITCOIN STYLE)
# ─────────────────────────────
class Wallet:
    def __init__(self):
        self.sk = SigningKey.generate(curve=SECP256k1)
        self.vk = self.sk.get_verifying_key()

    def address(self):
        pub = self.vk.to_string().hex()
        return hashlib.sha256(pub.encode()).hexdigest()

    def sign(self, message):
        return self.sk.sign(message.encode()).hex()

    def verify(self, message, signature, pubkey_hex):
        try:
            vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
            return vk.verify(bytes.fromhex(signature), message.encode())
        except BadSignatureError:
            return False


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

    def load_chain(self):
        if not os.path.exists(CHAIN_FILE):
            genesis = Block(0, "0"*64, [])
            self.chain = [genesis]
            self.save()
            return

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

    def save(self):
        with open(CHAIN_FILE, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    # ───────── BALANCE ─────────
    def balance(self, addr):
        bal = 0
        for b in self.chain:
            for tx in b.data:
                if tx["to"] == addr:
                    bal += tx["amount"]
                if tx["from"] == addr:
                    bal -= tx["amount"]
        return bal

    # ───────── VERIFY TX ─────────
    def verify_tx(self, tx):
        if tx["from"] == "SYSTEM":
            return True

        msg = f"{tx['from']}{tx['to']}{tx['amount']}{tx['timestamp']}"
        try:
            vk = VerifyingKey.from_string(bytes.fromhex(tx["pubkey"]), curve=SECP256k1)
            return vk.verify(bytes.fromhex(tx["signature"]), msg.encode())
        except:
            return False

    # ───────── TX ─────────
    def add_tx(self, tx):
        if self.verify_tx(tx):
            self.mempool.append(tx)
            return True
        return False

    # ───────── MINE ─────────
    def mine(self, miner):
        reward = {
            "from": "SYSTEM",
            "to": miner,
            "amount": 50,
            "timestamp": int(time.time()),
            "pubkey": "",
            "signature": ""
        }

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
        "status": "DYNAX SECURE NODE ACTIVE",
        "blocks": len(node.chain)
    }


@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])


@app.route("/balance/<addr>")
def balance(addr):
    return {"address": addr, "balance": node.balance(addr)}


@app.route("/tx", methods=["POST"])
def tx():
    data = request.json
    ok = node.add_tx(data)

    if not ok:
        return {"error": "invalid signature"}, 400

    return {"status": "accepted"}


@app.route("/mine/<miner>")
def mine(miner):
    return jsonify(node.mine(miner).to_dict())


if __name__ == "__main__":
    print("=== DYNAX SECURE NODE STARTED ===")
    app.run(host="0.0.0.0", port=6001)
