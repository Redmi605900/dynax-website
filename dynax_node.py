import time
import json
import hashlib
import requests
import os
import hmac
import threading
import ecdsa
import binascii
from flask import Flask, request, jsonify, make_response

CHAIN_FILE = os.path.expanduser("~/dynax_chain.json")
PEERS_FILE = os.path.expanduser("~/dynax_peers.json")
DIFFICULTY = 4
INITIAL_BLOCK_REWARD = 50
HALVING_INTERVAL = 210000  # blocks
TARGET_BLOCK_TIME = 12   # วินาที
ADJUSTMENT_INTERVAL = 10  # ปรับทุก 10 blocks

def get_block_reward(block_index):
    halvings = block_index // HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return INITIAL_BLOCK_REWARD / (2 ** halvings)
SECRET_KEY = "DYNAX_SECRET_v1"

def pubkey_to_address(public_key_hex):
    pub_bytes = binascii.unhexlify(public_key_hex)
    return "DX" + hashlib.sha3_256(pub_bytes).hexdigest()[:40]
PORT = int(os.environ.get("PORT", 6001))

# ─────────────────────────────────────────────
class Block:
# ─────────────────────────────────────────────
    def __init__(self, index, prev_hash, txs, nonce=0, difficulty=DIFFICULTY):
        self.index = index
        self.timestamp = int(time.time())
        self.prev_hash = prev_hash
        self.transactions = txs
        self.nonce = nonce
        self.difficulty = difficulty
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
            "difficulty": self.difficulty,
            "hash": self.hash,
            "tx_count": len(self.transactions)
        }

# ─────────────────────────────────────────────
class DYNAXNode:
# ─────────────────────────────────────────────
    def __init__(self):
        self.chain = []
        self.mempool = []
        self.peers = set()   # ใช้ set เพื่อกัน duplicate
        self.lock = threading.Lock()
        self.load_chain()
        self.load_peers()
        # auto-sync หลัง boot (รอ 3 วิให้ Flask พร้อมก่อน)
        threading.Timer(3.0, self.sync_from_peers).start()

    # ── Persistence ──────────────────────────
    def save_chain(self):
        with open(CHAIN_FILE, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def save_peers(self):
        with open(PEERS_FILE, "w") as f:
            json.dump(list(self.peers), f)

    def load_peers(self):
        if os.path.exists(PEERS_FILE):
            with open(PEERS_FILE) as f:
                peers = json.load(f)
            for p in peers:
                self.peers.add(p)
            print(f"📡 Loaded {len(self.peers)} peers from file")

    def load_chain(self):
        if not os.path.exists(CHAIN_FILE):
            genesis_txs = [
                {"from": "GENESIS", "to": pubkey_to_address("300b89357df0bd3d42ee24d0305c98a7fe1a8ba5885a8016b2fa5f742b5f427ca4f0343f299bb4e6ea29e12ebc9564e79fc4be0281847d1c93089dcbc545293c"), "amount": 300000},
                {"from": "GENESIS", "to": pubkey_to_address("4d5e1f2e511e2eeff12319676ef1da8a037a68a739bcb222b2f9066a8d4643b6a5f964e71953bdfdabee50790c533ee849f7bbde2a904f08c53e3d0903985f73"), "amount": 7000},
                {"from": "GENESIS", "to": pubkey_to_address("69c6ff91c95622444b69d35af7f95ac7b7422c81ddf8a4a08a138de5428c1b376e876a523c593610bb9168f6f743b27d4fba5c1fd0d7bf7b567e7df97c0bbb9b"), "amount": 445},
                {"from": "GENESIS", "to": pubkey_to_address("7183f5718aede7299e3e8f8e23b94b96a601d36d50632b75238b710049d29871bb0ddb116f3fb9d84a284640a5ca3742620f9eb1894a76aa4ff645a639f86f1b"), "amount": 137}
            ]
            genesis = Block(0, "0" * 64, genesis_txs)
            self.chain.append(genesis)
            self.save_chain()
            return

        with open(CHAIN_FILE) as f:
            data = json.load(f)

        for item in data:
            b = Block(item["index"], item["prev_hash"], item["transactions"], item["nonce"])
            b.timestamp = item["timestamp"]
            b.difficulty = item.get("difficulty", DIFFICULTY)
            b.hash = item["hash"]
            self.chain.append(b)

    # ── Chain helpers ─────────────────────────
    def last_block(self):
        return self.chain[-1]

    def verify_chain(self, chain=None):
        chain = chain or self.chain
        for i in range(1, len(chain)):
            curr = chain[i]
            prev = chain[i - 1]
            # รองรับทั้ง Block object และ dict
            curr_prev = curr.prev_hash if hasattr(curr, "prev_hash") else curr["prev_hash"]
            prev_hash  = prev.hash     if hasattr(prev,  "hash")     else prev["hash"]
            curr_hash  = curr.hash     if hasattr(curr,  "hash")     else curr["hash"]
            curr_calc  = curr.calculate_hash() if hasattr(curr, "calculate_hash") else None

            if curr_prev != prev_hash:
                return False
            if curr_calc and curr_hash != curr_calc:
                return False
        return True

    # ── Difficulty Adjustment ────────────────
    def adjust_difficulty(self):
        if len(self.chain) % ADJUSTMENT_INTERVAL != 0:
            return self.chain[-1].difficulty if hasattr(self.chain[-1], "difficulty") else DIFFICULTY

        # เอา 10 blocks ล่าสุด
        last = self.chain[-ADJUSTMENT_INTERVAL]
        now  = self.chain[-1]
        elapsed = now.timestamp - last.timestamp

        current_diff = now.difficulty if hasattr(now, "difficulty") else DIFFICULTY

        if elapsed == 0:
            return current_diff

        # คำนวณ difficulty ใหม่
        expected = TARGET_BLOCK_TIME * ADJUSTMENT_INTERVAL
        ratio = elapsed / expected

        if ratio < 0.5:
            new_diff = current_diff + 1
        elif ratio > 2.0:
            new_diff = max(1, current_diff - 1)
        else:
            new_diff = current_diff

        if new_diff != current_diff:
            print(f"⚡ Difficulty adjusted: {current_diff} → {new_diff} (elapsed={elapsed}s)")
        return new_diff

    # ── P2P: Broadcast ───────────────────────
    def broadcast_block(self, block):
        def _send(peer):
            try:
                requests.post(peer + "/receive_block", json=block.to_dict(), timeout=2)
            except Exception:
                pass

        for peer in list(self.peers):
            threading.Thread(target=_send, args=(peer,), daemon=True).start()

    # ── P2P: Fetch chain from peer ───────────
    def fetch_chain_from_peer(self, peer):
        try:
            r = requests.get(peer + "/chain", timeout=3)
            return r.json()   # list of dicts
        except Exception:
            return None

    # ── P2P: Sync (longest chain wins) ───────
    def sync_from_peers(self):
        best_raw = None
        best_len = len(self.chain)

        for peer in list(self.peers):
            raw = self.fetch_chain_from_peer(peer)
            if raw and isinstance(raw, list) and len(raw) > best_len:
                # ตรวจสอบ chain ก่อน accept
                if self._validate_raw_chain(raw):
                    best_raw = raw
                    best_len = len(raw)

        if best_raw:
            with self.lock:
                self.chain = self._raw_to_blocks(best_raw)
                self.save_chain()
            return True
        return False

    def _validate_raw_chain(self, raw):
        for i in range(1, len(raw)):
            if raw[i]["prev_hash"] != raw[i - 1]["hash"]:
                return False
            b = Block(raw[i]["index"], raw[i]["prev_hash"], raw[i]["transactions"], raw[i]["nonce"])
            b.timestamp = raw[i]["timestamp"]
            if b.calculate_hash() != raw[i]["hash"]:
                return False
        return True

    def _raw_to_blocks(self, raw):
        blocks = []
        for item in raw:
            b = Block(item["index"], item["prev_hash"], item["transactions"], item["nonce"])
            b.timestamp = item["timestamp"]
            b.difficulty = item.get("difficulty", DIFFICULTY)
            b.hash = item["hash"]
            blocks.append(b)
        return blocks

    # ── Peers management ─────────────────────
    def add_peer(self, peer_url):
        peer_url = peer_url.rstrip("/")
        self.peers.add(peer_url)
        self.save_peers()

    # ── Balance ──────────────────────────────
    def get_balance(self, address):
        balance = 0
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("from") == address:
                    balance -= tx["amount"]
                if tx.get("to") == address:
                    balance += tx["amount"]
        return balance

    # ── Transaction ──────────────────────────
    def add_transaction(self, tx):
        for field in ["from", "to", "amount", "signature", "public_key"]:
            if field not in tx:
                return {"success": False, "error": f"missing {field}"}
        if tx["amount"] <= 0:
            return {"success": False, "error": "invalid amount"}
        balance = self.get_balance(tx["from"])
        if balance < tx["amount"] and tx["from"] != "GENESIS":
            return {"success": False, "error": f"insufficient balance: {balance}"}

        tx_canonical = {"from": tx["from"], "to": tx["to"], "amount": tx["amount"]}
        message = json.dumps(tx_canonical, sort_keys=True).encode()

        # ── ECDSA Signature Verification ─────────
        if "public_key" not in tx:
            return {"success": False, "error": "missing public_key"}
        try:
            # ตรวจว่า public_key ตรงกับ address
            expected_address = pubkey_to_address(tx["public_key"])
            if expected_address != tx["from"]:
                return {"success": False, "error": "public_key does not match address"}
            vk = ecdsa.VerifyingKey.from_string(
                binascii.unhexlify(tx["public_key"]),
                curve=ecdsa.SECP256k1,
                hashfunc=hashlib.sha256
            )
            sig_bytes = binascii.unhexlify(tx["signature"])
            if not vk.verify(sig_bytes, message):
                return {"success": False, "error": "invalid signature"}
        except Exception as e:
            return {"success": False, "error": f"signature error: {str(e)}"}
        # ─────────────────────────────────────────

        txid = hashlib.sha3_256(json.dumps(tx_canonical, sort_keys=True).encode()).hexdigest()

        # ── Double-spend protection ──────────────
        # 1. เช็คใน mempool
        for pending in self.mempool:
            if pending.get("txid") == txid:
                return {"success": False, "error": "tx already in mempool"}

        # 2. เช็คใน chain
        for block in self.chain:
            for confirmed in block.transactions:
                if confirmed.get("txid") == txid:
                    return {"success": False, "error": "tx already confirmed"}

        # 3. เช็ค balance รวม pending ใน mempool
        pending_out = sum(
            t["amount"] for t in self.mempool
            if t.get("from") == tx["from"]
        )
        if balance - pending_out < tx["amount"] and tx["from"] != "GENESIS":
            return {"success": False, "error": f"insufficient balance (including pending): {balance - pending_out}"}
        # ─────────────────────────────────────────

        tx["txid"] = txid
        tx["timestamp"] = int(time.time())
        self.mempool.append(tx)
        return {"success": True, "txid": tx["txid"]}

    # ── Mining ───────────────────────────────
    def mine(self, miner_address):
        reward = get_block_reward(len(self.chain))
        reward_tx = {
            "from": "NETWORK",
            "to": miner_address,
            "amount": reward,
            "txid": hashlib.sha3_256(f"reward_{len(self.chain)}".encode()).hexdigest()
        }
        txs = [reward_tx] + self.mempool[:]
        diff = self.adjust_difficulty()
        block = Block(len(self.chain), self.last_block().hash, txs, difficulty=diff)

        print(f"⛏️  Mining block #{block.index} (difficulty={diff})...")
        while not block.hash.startswith("0" * diff):
            block.nonce += 1
            block.hash = block.calculate_hash()

        with self.lock:
            self.chain.append(block)
            self.mempool = []
            self.save_chain()

        self.broadcast_block(block)
        print(f"✅ Block #{block.index} mined: {block.hash[:20]}...")
        return block

    # ── TX lookup ────────────────────────────
    def get_tx(self, txid):
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("txid") == txid:
                    return {"tx": tx, "block": block.index}
        return None

    # ── Info ─────────────────────────────────
    def info(self):
        return {
            "name": "DYNAX",
            "symbol": "DYX",
            "version": "2.5.0",
            "blocks": len(self.chain),
            "mempool": len(self.mempool),
            "peers": len(self.peers),
            "difficulty": DIFFICULTY,
            "reward": get_block_reward(len(self.chain)),
            "next_halving": HALVING_INTERVAL - (len(self.chain) % HALVING_INTERVAL),
            "max_supply": 11000000,
            "valid": self.verify_chain()
        }


# ═════════════════════════════════════════════
# Flask API
# ═════════════════════════════════════════════
app = Flask(__name__)
node = DYNAXNode()

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return make_response("", 204)

# ── Info ──────────────────────────────────────
@app.route("/")
def index():
    return jsonify(node.info())

# ── Chain ─────────────────────────────────────
@app.route("/chain")
def get_chain():
    return jsonify([b.to_dict() for b in node.chain])

@app.route("/block/<int:index>")
def get_block(index):
    if index < len(node.chain):
        return jsonify(node.chain[index].to_dict())
    return jsonify({"error": "block not found"}), 404

# ── Receive block from peer ───────────────────
@app.route("/receive_block", methods=["POST"])
def receive_block():
    data = request.get_json()

    b = Block(data["index"], data["prev_hash"], data["transactions"], data["nonce"])
    b.timestamp = data["timestamp"]
    b.hash = data["hash"]

    # ตรวจ: ต้องต่อจาก block ล่าสุด
    if b.prev_hash != node.last_block().hash:
        return jsonify({"status": "rejected", "reason": "bad chain"})

    # ตรวจ: hash ต้องถูกต้อง
    if b.calculate_hash() != b.hash:
        return jsonify({"status": "rejected", "reason": "invalid hash"})

    with node.lock:
        node.chain.append(b)
        node.save_chain()

    return jsonify({"status": "accepted", "block": b.index})

# ── TX ────────────────────────────────────────
@app.route("/tx/<txid>")
def get_tx(txid):
    result = node.get_tx(txid)
    if result:
        return jsonify(result)
    return jsonify({"error": "tx not found"}), 404

# ── Balance ───────────────────────────────────
@app.route("/balance/<address>")
def balance(address):
    return jsonify({"address": address, "balance": node.get_balance(address), "symbol": "DYX"})

# ── Mempool ───────────────────────────────────
@app.route("/mempool")
def mempool():
    return jsonify({"mempool": node.mempool, "count": len(node.mempool)})

# ── Send TX ───────────────────────────────────
@app.route("/send", methods=["POST"])
def send():
    tx = request.get_json()
    return jsonify(node.add_transaction(tx))

# ── Mine ──────────────────────────────────────
@app.route("/mine/<address>")
def mine(address):
    block = node.mine(address)
    # trigger consensus บน peers หลัง mine
    threading.Thread(
        target=lambda: [
            requests.get(f"{p}/consensus", timeout=3)
            for p in list(node.peers)
        ],
        daemon=True
    ).start()
    return jsonify({"success": True, "block": block.to_dict()})

# ── Peers ─────────────────────────────────────
@app.route("/peers")
def peers():
    return jsonify({"peers": list(node.peers), "count": len(node.peers)})

@app.route("/peers/add", methods=["POST"])
def add_peer():
    data = request.get_json()
    peer = data.get("peer", "").rstrip("/")
    if peer and peer not in node.peers:
        node.add_peer(peer)
        # แจ้ง peer กลับว่าเราอยู่ที่ไหน (handshake)
        my_url = data.get("self_url", "")
        if my_url:
            try:
                requests.post(peer + "/peers/add", json={"peer": my_url}, timeout=2)
            except Exception:
                pass
    return jsonify({"peers": list(node.peers)})

# ── Sync (pull longest chain) ─────────────────
@app.route("/sync", methods=["POST"])
def sync():
    replaced = node.sync_from_peers()
    return jsonify({"replaced": replaced, "length": len(node.chain)})

# ── Consensus (push: peer calls us to sync) ───
@app.route("/consensus", methods=["GET"])
def consensus():
    replaced = node.sync_from_peers()
    return jsonify({"replaced": replaced, "length": len(node.chain)})

# ── Peer Discovery ────────────────────────────
@app.route("/peers/discover", methods=["POST"])
def discover_peers():
    new_peers = 0
    for peer in list(node.peers):
        try:
            r = requests.get(peer + "/peers", timeout=3)
            data = r.json()
            for p in data.get("peers", []):
                if p and p not in node.peers and p != request.host_url.rstrip("/"):
                    node.add_peer(p)
                    new_peers += 1
        except:
            pass
    return jsonify({"new_peers": new_peers, "total": len(node.peers), "peers": list(node.peers)})

# ── Halving info ──────────────────────────────
@app.route("/halving")
def halving():
    current = len(node.chain)
    halvings_done = current // HALVING_INTERVAL
    return jsonify({
        "current_block": current,
        "halvings_done": halvings_done,
        "current_reward": get_block_reward(current),
        "next_halving_block": (halvings_done + 1) * HALVING_INTERVAL,
        "blocks_until_halving": HALVING_INTERVAL - (current % HALVING_INTERVAL)
    })


# ═════════════════════════════════════════════
if __name__ == "__main__":
    print("=== DYNAX Node v2.5.0 ===")
    print(json.dumps(node.info(), indent=2))
    print(f"\n🌐 Running on http://0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
