import socket
import threading
import json
import time
import hashlib
import os
from flask import Flask, jsonify

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", 6001))
SOCKET_PORT = PORT + 1000
PEERS = [
    ("127.0.0.1", 6002),
    ("127.0.0.1", 6003)
]

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
        self.lock = threading.Lock()

    def add_block(self, data):
        with self.lock:
            last = self.chain[-1]
            block = Block(len(self.chain), last.hash, data)

            while not block.hash.startswith("0000"):
                block.nonce += 1
                block.hash = block.calc_hash()

            self.chain.append(block)
            self.broadcast(block)
            return block

    def receive_block(self, block_data):
        with self.lock:
            block = Block(
                block_data["index"],
                block_data["prev_hash"],
                block_data["data"],
                block_data["timestamp"],
                block_data["nonce"]
            )
            self.chain.append(block)

    def broadcast(self, block):
        msg = json.dumps(block.to_dict()).encode()

        for host, port in PEERS:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((host, port))
                s.send(msg)
                s.close()
            except:
                pass


node = Node()


# ─────────────────────────────
# SOCKET SERVER
# ─────────────────────────────
def socket_server():
    import socket
    import json

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # กัน port ค้าง / restart แล้ว error
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    SOCKET_PORT = PORT + 1000

    s.bind((HOST, SOCKET_PORT))
    s.listen()

    print(f"⚡ P2P SOCKET RUNNING ON {SOCKET_PORT}")

    while True:
        conn, addr = s.accept()
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
        "status": "DYNAX P2P BITCOIN NETWORK",
        "blocks": len(node.chain),
        "port": PORT
    }


@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])


@app.route("/mine/<data>")
def mine(data):
    return jsonify(node.add_block({"data": data}).to_dict())


# ─────────────────────────────
# START
# ─────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=socket_server, daemon=True).start()

    print("=== DYNAX REAL P2P NODE STARTED ===")
    app.run(host="0.0.0.0", port=PORT)
