import os
import time
import json
import hashlib
import socket
import threading
from flask import Flask, request, jsonify

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", 6001))
P2P_PORT = PORT + 1000

PEERS = [
    ("127.0.0.1", 6002),
    ("127.0.0.1", 6003),
]

DIFFICULTY = 4

app = Flask(__name__)

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
        self.chain = [Block(0, "0"*64, {"genesis": True})]
        self.mempool = []
        self.seen = set()
        self.lock = threading.Lock()

    # ───────── VALIDATION ─────────
    def valid_block(self, prev, block):
        if block.prev_hash != prev.hash:
            return False
        if not block.hash.startswith("0" * DIFFICULTY):
            return False
        return True

    # ───────── CONSENSUS ─────────
    def resolve_chain(self, incoming):
        if len(incoming) > len(self.chain):
            self.chain = incoming
            return True
        return False

    # ───────── ADD BLOCK ─────────
    def add_block(self, data):
        with self.lock:
            last = self.chain[-1]
            block = Block(len(self.chain), last.hash, data)

            while not block.hash.startswith("0" * DIFFICULTY):
                block.nonce += 1
                block.hash = block.calc_hash()

            self.chain.append(block)
            self.seen.add(block.hash)

            self.broadcast(block.to_dict())
            return block

    # ───────── RECEIVE BLOCK ─────────
    def receive_block(self, block_data):
        with self.lock:
            if block_data["hash"] in self.seen:
                return

            prev = self.chain[-1]
            block = Block(
                block_data["index"],
                block_data["prev_hash"],
                block_data["data"],
                block_data["timestamp"],
                block_data["nonce"]
            )

            if self.valid_block(prev, block):
                self.chain.append(block)
                self.seen.add(block.hash)
                self.broadcast(block.to_dict())

    # ───────── GOSSIP BROADCAST ─────────
    def broadcast(self, block):
        msg = json.dumps(block).encode()

        for host, port in PEERS:
            try:
                s = socket.socket()
                s.connect((host, port + 1000))
                s.send(msg)
                s.close()
            except:
                pass

# ─────────────────────────────
node = Node()

# ─────────────────────────────
# SOCKET P2P LAYER
# ─────────────────────────────
def socket_server():
    import socket
    import json

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    P2P_PORT = PORT + 1000

    s.bind((HOST, P2P_PORT))
    s.listen()

    print(f"⚡ P2P RUNNING ON {P2P_PORT}")

    while True:
        conn, _ = s.accept()
        data = conn.recv(65536)

        try:
            block = json.loads(data.decode())
            node.receive_block(block)
        except:
            pass

        conn.close()
# ─────────────────────────────
# HTTP API
# ─────────────────────────────
@app.route("/")
def home():
    return {
        "status": "DYNAX MINI BITCOIN CORE",
        "blocks": len(node.chain),
        "port": PORT
    }

@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])

@app.route("/mine/<data>")
def mine(data):
    block = node.add_block({"data": data})
    return jsonify(block.to_dict())

@app.route("/tx", methods=["POST"])
def tx():
    node.mempool.append(request.json)
    return {"status": "queued"}

# ─────────────────────────────
# START
# ─────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=socket_server, daemon=True).start()

    print("=== DYNAX MINI BITCOIN CORE STARTED ===")
    app.run(host="0.0.0.0", port=PORT)
