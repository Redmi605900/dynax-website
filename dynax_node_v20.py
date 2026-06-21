import time
import requests
import threading
import json
import hashlib
import os
from flask import Flask, jsonify, request
from ecdsa import VerifyingKey, SECP256k1

app = Flask(__name__)

def pubkey_to_address(pubkey_bytes):
    h = hashlib.sha3_256(pubkey_bytes).hexdigest()
    return "DX" + h[:40]

def verify_signature(from_addr, msg_text, sig_hex):
    try:
        sig = bytes.fromhex(sig_hex)
        msg = msg_text.encode()
        vks = VerifyingKey.from_public_key_recovery(sig, msg, SECP256k1, hashfunc=hashlib.sha3_256)
        for vk in vks:
            addr = pubkey_to_address(vk.to_string())
            if addr.lower() == from_addr.lower():
                return True
        return False
    except Exception as e:
        print("Sig error:", e)
        return False

class DynaxNode:
    def __init__(self):
        self.chain = []
        self.mempool = []
        self.peers = set()
        self.CHAIN_FILE = "dynax_chain.json"
        self.load_chain()

# Load chain from backup if exists
import os
if os.path.exists('chain_backup.json'):
    try:
        with open('chain_backup.json', 'r') as f:
            backup_chain = json.load(f)
            if isinstance(backup_chain, list) and len(backup_chain) > len(blockchain):
                blockchain.clear()
                blockchain.extend(backup_chain)
                print(f"Loaded {len(blockchain)} blocks from chain_backup.json")
    except Exception as e:
        print(f"Error loading backup: {e}")


    def load_chain(self):
        if os.path.exists(self.CHAIN_FILE):
            try:
                with open(self.CHAIN_FILE, "r") as f: self.chain = json.load(f)
                print(f"Loaded {len(self.chain)} blocks")
            except Exception as e: print("Error:", e)
        else: self.create_genesis()

    def create_genesis(self):
        genesis = {
            "index": 0,
            "timestamp": 1780771234,
            "transactions": [
                {"from": "GENESIS", "to": "DXa5ae9ccc94279d4f52b4f4e694a5a3b2f4f5ece3", "amount": 300000},
                {"from": "GENESIS", "to": "DX2cd2db91dd4e11e56b3a90e8219b9b11f16d498d", "amount": 7000},
                {"from": "GENESIS", "to": "DXb2913cfc7756e6675fadbcb35cd595e680b330d3", "amount": 445},
                {"from": "GENESIS", "to": "DXe0e2eb885049e91123a0ab6f4bf62064d4572170", "amount": 137}
            ],
            "prev_hash": "0"*64,
            "nonce": 0
        }
        genesis["hash"] = hashlib.sha3_256(json.dumps(genesis, sort_keys=True).encode()).hexdigest()
        self.chain = [genesis]
        self.save_chain()

    def save_chain(self):
        tmp = self.CHAIN_FILE + ".tmp"
        with open(tmp, "w") as f: json.dump(self.chain, f, indent=2)
        os.replace(tmp, self.CHAIN_FILE)

    def get_txs(self, b): return b.get("transactions") or b.get("txs") or b.get("data") or []

    def balance(self, addr):
        bal = 0
        for b in self.chain:
            for tx in self.get_txs(b):
                if tx.get("to") == addr: bal += tx.get("amount", 0)
                if tx.get("from") == addr: bal -= tx.get("amount", 0)
        return bal

    def send(self, sender, receiver, amount, fee, signature):
        amount = float(amount)
        fee = float(fee)
        if amount <= 0: return {"error": "invalid amount"}
        if self.balance(sender) < amount + fee: return {"error": "insufficient balance"}
        msg_dict = {"amount": amount, "fee": fee, "from": sender, "to": receiver}
        msg_text = json.dumps(msg_dict, sort_keys=True, separators=(",", ":"))
        if not verify_signature(sender, msg_text, signature): return {"error": "invalid signature"}
        tx = {"from": sender, "to": receiver, "amount": amount, "fee": fee, "signature": signature, "timestamp": int(time.time())}
        self.mempool.append(tx)
        return {"status": "queued", "tx": tx}

    def mine(self, miner):
        if not self.mempool: return {"error": "no tx"}
        reward = {"from": "SYSTEM", "to": miner, "amount": 50, "timestamp": int(time.time())}
        txs = self.mempool[:50]
        self.mempool = self.mempool[50:]
        prev_hash = self.chain[-1]["hash"] if self.chain else "0"*64
        block = {"index": len(self.chain), "timestamp": int(time.time()), "transactions": [reward] + txs, "prev_hash": prev_hash, "nonce": 0}
        while True:
            raw = json.dumps(block, sort_keys=True)
            h = hashlib.sha3_256(raw.encode()).hexdigest()
            if h.startswith("0000"):
                block["hash"] = h
                break
            block["nonce"] += 1
        self.chain.append(block)
        self.save_chain()
        
        # Broadcast new block to all peers
        for peer in list(self.peers):
            try:
                r = requests.post(f"{peer}/receive_block", json=block, timeout=3)
                print(f"Broadcasted block {block['index']} to {peer}: {r.status_code}")
            except Exception as e:
                print(f"Failed to broadcast to {peer}: {e}")
        
        return {"status": "mined", "block": block["index"]}

node = DynaxNode()

@app.route("/tx", methods=["POST"])
def tx():
    data = request.get_json()
    if not all(k in data for k in ["from", "to", "amount", "signature"]): return jsonify({"error": "Missing fields"}), 400
    res = node.send(data["from"], data["to"], data["amount"], data.get("fee", 0), data["signature"])
    if "error" in res: return jsonify(res), 400
    return jsonify(res), 201

@app.route("/chain")
def get_chain(): return jsonify(node.chain)

@app.route("/balance/<addr>")
def balance(addr): return jsonify({"address": addr, "balance": node.balance(addr)})

@app.route("/mine/<miner>")
def mine(miner): return jsonify(node.mine(miner))

@app.route("/")
def home(): return jsonify({"network": "DYNAX v20 Secure", "blocks": len(node.chain)})


@app.route("/wallet")
def wallet_page():
    try:
        return open("wallet.html").read()
    except:
        return "wallet.html not found", 404

@app.route("/txs/<addr>")
def get_txs(addr):
    txs = []
    for b in node.chain:
        for tx in node.get_txs(b):
            if tx.get("to") == addr or tx.get("from") == addr:
                txs.append({**tx, "block": b["index"], "timestamp": b.get("timestamp", 0)})
    return jsonify(txs)

@app.route("/blocks")
def get_blocks():
    return jsonify(node.chain)


@app.route("/wallet_bilingual")
def wallet_bilingual():
    try:
        return open("wallet_bilingual.html").read()
    except:
        return "File not found", 404


@app.route("/landing")
def landing():
    try:
        return open("landing.html").read()
    except:
        return "Not found", 404


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.route("/test_wallet")
def test_wallet():
    try:
        return open("test_wallet.html").read()
    except:
        return "Not found", 404


@app.route("/auto")
def auto_login():
    try:
        return open("auto_login.html").read()
    except:
        return "Not found", 404


@app.route("/test_fetch")
def test_fetch():
    return open("test_fetch.html").read()



@app.route("/all")
def all_wallets():
    try:
        return open("all_wallets.html").read()
    except Exception as e:
        return f"Error: {e}", 500


def decrypt_wallet(encrypted_hex, password):
    key = hashlib.sha256(password.encode()).digest()
    encrypted = bytes.fromhex(encrypted_hex)
    decrypted = bytes([b ^ key[i % 32] for i, b in enumerate(encrypted)])
    return decrypted.decode()

@app.route("/wallet/unlock", methods=["POST"])
def wallet_unlock():
    data = request.json
    address = data.get('address')
    password = data.get('password')
    
    try:
        with open("wallets/wallet_encrypted.json", "r") as f:
            wallet = json.load(f)
        
        if wallet['address'] != address:
            return jsonify({"error": "Address ไม่ตรงกัน"}), 400
        
        if not wallet.get('encrypted'):
            return jsonify({"error": "Wallet ไม่ได้ encrypt"}), 400
        
        # Decrypt private key
        private_key = decrypt_wallet(wallet['private_key_encrypted'], password)
        
        return jsonify({
            "address": wallet['address'],
            "private_key": private_key
        })
    except Exception as e:
        return jsonify({"error": "รหัสผ่านไม่ถูกต้อง"}), 401




@app.route("/tx/send", methods=["POST"])
def send_tx_with_key():
    """ส่งธุรกรรมโดยเซ็นด้วย private_key ที่ส่งมา"""
    from ecdsa import SigningKey, SECP256k1
    
    data = request.json
    from_addr = data.get('from')
    to_addr = data.get('to')
    amount = data.get('amount')
    fee = data.get('fee', 0.01)
    private_key_hex = data.get('private_key')
    
    if not all([from_addr, to_addr, amount, private_key_hex]):
        return jsonify({"error": "ข้อมูลไม่ครบ"}), 400
    
    try:
        # สร้าง signature จาก private key
        sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
        
        msg_dict = {"amount": amount, "fee": fee, "from": from_addr, "to": to_addr}
        msg_text = json.dumps(msg_dict, sort_keys=True)
        msg_hash = hashlib.sha3_256(msg_text.encode()).digest()
        
        signature = sk.sign(msg_hash).hex()
        
        # สร้าง transaction
        tx = {
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "fee": fee,
            "signature": signature
        }
        
        # เพิ่มเข้า mempool ของ node
        node.mempool.append(tx)
        
        return jsonify({
            "message": "Transaction added to mempool",
            "mempool_size": len(node.mempool),
            "tx": tx
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/pending")
def show_pending():
    return jsonify({
        "count": len(node.mempool),
        "transactions": node.mempool
    })


@app.route("/stats")
def stats():
    chain = bc.chain
    txs = sum(len(bc.get_txs(b)) for b in chain)
    return jsonify({
        "blocks": len(chain),
        "transactions": txs,
        "nodes": 1,
        "difficulty": bc.difficulty,
        "symbol": "DYX",
        "reward": 50,
        "status": "online"
    })

@app.route("/peers")
def get_peers():
    return jsonify({"peers": list(node.peers)})

@app.route("/peers/add", methods=["POST"])
def add_peer():
    data = request.json
    peer = data.get("peer")
    if not peer:
        return jsonify({"error": "no peer"}), 400
    node.peers.add(peer)
    return jsonify({"status": "added", "peer": peer})

@app.route("/receive_block", methods=["POST"])
def receive_block():
    block = request.json
    if not block:
        return jsonify({"error": "no block"}), 400
    # เช็ก index ไม่ซ้ำ
    if any(b["index"] == block["index"] for b in node.chain):
        return jsonify({"status": "already have"}), 200
    # เช็ก prev_hash ต่อกัน
    if node.chain and block.get("prev_hash") != node.chain[-1]["hash"]:
        return jsonify({"error": "invalid prev_hash"}), 400
    node.chain.append(block)
    node.save_chain()
    return jsonify({"status": "accepted", "block": block["index"]})

@app.route("/sync")
def sync_chain():
    longest = node.chain
    for peer in node.peers:
        try:
            r = requests.get(f"{peer}/chain", timeout=3)
            peer_chain = r.json()
            if len(peer_chain) > len(longest):
                longest = peer_chain
        except:
            pass
    if len(longest) > len(node.chain):
        node.chain = longest
        node.save_chain()
        return jsonify({"status": "synced", "blocks": len(node.chain)})
    return jsonify({"status": "already longest", "blocks": len(node.chain)})


@app.route("/assets/<path:filename>")
def assets(filename):
    import os
    filepath = os.path.join("assets", filename)
    if os.path.exists(filepath):
        from flask import send_file
        return send_file(filepath)
    return "Not found", 404

if __name__ == "__main__":
    print("=== DYNAX V20 SECURE NODE STARTED ===")
    app.run(host="0.0.0.0", port=6002)