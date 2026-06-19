import os
import time
import json
import hashlib
import socket
import threading
from flask import Flask, jsonify

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", 6001))
P2P_PORT = PORT + 1000

PEERS = [
    ("127.0.0.1", 6002),
    ("127.0.0.1", 6003),
]

DIFFICULTY = 4
app = Flask(__name__)


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


class Node:
    def __init__(self):
        self.chain = [Block(0, "0"*64, {"genesis": True})]
        self.lock = threading.Lock()
        self.seen = set()

    def valid_block(self, prev, block):
        return block.prev_hash == prev.hash and block.hash.startswith("0" * DIFFICULTY)

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

    def receive_block(self, block_data):
        with self.lock:
            if block_data["hash"] in self.seen:
                return

            last = self.chain[-1]

            block = Block(
                block_data["index"],
                block_data["prev_hash"],
                block_data["data"],
                block_data["timestamp"],
                block_data["nonce"]
            )

            if self.valid_block(last, block):
                self.chain.append(block)
                self.seen.add(block.hash)

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


node = Node()


def socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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


@app.route("/")
def home():
    return {"status": "OK", "blocks": len(node.chain)}

@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in node.chain])

@app.route("/mine/<data>")
def mine(data):
    return jsonify(node.add_block({"data": data}).to_dict())


if __name__ == "__main__":
    threading.Thread(target=socket_server, daemon=True).start()
    print("=== DYNAX FULL NETWORK STARTED ===")
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)
