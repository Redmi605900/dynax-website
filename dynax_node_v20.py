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
def home(): return jsonify({"network": "DYNAX v20 Secure", "blocks": len(node.chain), "api_v1": True})


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
    chain = node.chain
    txs = sum(len(node.get_txs(b)) for b in chain)
    return jsonify({
        "blocks": len(chain),
        "transactions": txs,
        "nodes": len(node.peers) + 1,
        "difficulty": "0000",
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


@app.route("/explorer")
def explorer():
    try:
        return open("explorer.html").read()
    except:
        return "explorer.html not found", 404

@app.route("/whitepaper")
def whitepaper():
    try:
        return open("whitepaper.html").read()
    except:
        return "whitepaper.html not found", 404

@app.route("/dex")
def dex():
    try:
        return open("dex.html").read()
    except:
        return "dex.html not found", 404


def auto_connect_bootstrap():
    # Static peers
    static_peers = [
        "https://dynax-node.onrender.com",
    ]
    for p in static_peers:
        node.peers.add(p)

    import time
    time.sleep(10)
    bootstrap = os.environ.get("BOOTSTRAP_NODE", "")
    if bootstrap:
        try:
            import requests
            requests.post(f"{bootstrap}/peers/add", json={"peer": os.environ.get("MY_URL", "")}, timeout=5)
            node.peers.add(bootstrap)
            print(f"Connected to bootstrap: {bootstrap}")
        except Exception as e:
            print(f"Bootstrap connect failed: {e}")

import threading
threading.Thread(target=auto_connect_bootstrap, daemon=True).start()


# DEX Liquidity Pool
import json as _json

POOL_FILE = "liquidity_pool.json"

def load_pool():
    if os.path.exists(POOL_FILE):
        with open(POOL_FILE) as f:
            return _json.load(f)
    return {"DYX": 100000, "USDT": 50000}

def save_pool(pool):
    with open(POOL_FILE, "w") as f:
        _json.dump(pool, f)

liquidity_pool = load_pool()

@app.route("/dex/pool")
def dex_pool():
    price = liquidity_pool["USDT"] / liquidity_pool["DYX"]
    return jsonify({
        "DYX": liquidity_pool["DYX"],
        "USDT": liquidity_pool["USDT"],
        "price_dyx_usdt": round(price, 6)
    })

@app.route("/dex/swap", methods=["POST"])
def dex_swap():
    try:
        data = request.get_json()
        token_in = data["token_in"]
        token_out = data["token_out"]
        amount_in = float(data["amount_in"])
        if amount_in <= 0:
            return jsonify({"error": "Amount must be positive"}), 400
        reserve_in = liquidity_pool[token_in]
        reserve_out = liquidity_pool[token_out]
        amount_out = (amount_in * reserve_out) / (reserve_in + amount_in)
        liquidity_pool[token_in] += amount_in
        liquidity_pool[token_out] -= amount_out
        save_pool(liquidity_pool)
        return jsonify({
            "success": True,
            "swapped": f"{amount_in} {token_in} -> {round(amount_out,6)} {token_out}",
            "rate": round(amount_out/amount_in, 6),
            "pool": liquidity_pool
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/dex/liquidity", methods=["POST"])
def dex_add_liquidity():
    try:
        data = request.get_json()
        token = data["token"]
        amount = float(data["amount"])
        if amount <= 0:
            return jsonify({"error": "Amount must be positive"}), 400
        liquidity_pool[token] = liquidity_pool.get(token, 0) + amount
        save_pool(liquidity_pool)
        return jsonify({"success": True, "pool": liquidity_pool})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    print("=== DYNAX V20 SECURE NODE STARTED ===")
    
# ===== BRIDGE API v1 =====
@app.route("/api/v1/info")
def api_info():
    return jsonify({
        "network": "DYNAX",
        "version": "v20",
        "network_id": 1337,
        "ticker": "DYX",
        "max_supply": 11000000,
        "block_reward": 50,
        "algorithm": "SHA3-256 PoW",
        "blocks": len(node.chain),
        "status": "online"
    })

@app.route("/api/v1/balance/<addr>")
def api_balance(addr):
    bal = node.get_balance(addr)
    return jsonify({"address": addr, "balance": bal, "symbol": "DYX"})

@app.route("/api/v1/tx/<txid>")
def api_tx(txid):
    for block in node.chain:
        for tx in block.get("transactions", []):
            if tx.get("signature", "")[:16] == txid[:16]:
                return jsonify({"found": True, "tx": tx, "block": block["index"]})
    return jsonify({"found": False, "txid": txid}), 404

@app.route("/api/v1/blocks")
def api_blocks():
    limit = int(request.args.get("limit", 10))
    return jsonify({"total": len(node.chain), "blocks": node.chain[-limit:]})

@app.route("/api/v1/send", methods=["POST"])
def api_send():
    return send_tx_with_key()

@app.route("/api/v1/peers", methods=["GET"])
def api_peers():
    return jsonify({"peers": list(node.peers), "count": len(node.peers)})

@app.route("/api/v1/peers/add", methods=["POST"])
def api_peers_add():
    data = request.json
    peer = data.get("peer")
    if peer:
        node.peers.add(peer)
        return jsonify({"success": True, "peer": peer})
    return jsonify({"error": "peer required"}), 400




def broadcast_tx(tx):
    """ส่ง transaction ไปให้ทุก peer"""
    import requests as _req
    for peer in list(node.peers):
        try:
            _req.post(f"{peer}/receive_tx", json=tx, timeout=3)
        except:
            pass

@app.route("/receive_tx", methods=["POST"])
def receive_tx():
    """รับ transaction จาก peer"""
    tx = request.json
    if not tx:
        return jsonify({"error": "no tx"}), 400
    # เช็คว่ามีใน mempool แล้วหรือยัง
    for existing in node.mempool:
        if existing.get("signature") == tx.get("signature"):
            return jsonify({"status": "already have tx"})
    node.mempool.append(tx)
    # relay ต่อไปยัง peer อื่น
    threading.Thread(target=broadcast_tx, args=(tx,), daemon=True).start()
    return jsonify({"status": "received", "mempool_size": len(node.mempool)})

def validate_chain(chain):
    """ตรวจสอบ chain ว่าถูกต้องไหม"""
    import hashlib as _hl
    for i in range(1, len(chain)):
        block = chain[i]
        prev = chain[i-1]
        
        # เช็ค previous hash
        if block.get("prev_hash") != prev.get("hash"):
            print(f"Invalid prev_hash at block {i}")
            return False
        
        # เช็ค hash ของ block
        raw = _hl.sha3_256(
            __import__("json").dumps(
                {k: v for k, v in block.items() if k != "hash"}, 
                sort_keys=True
            ).encode()
        ).hexdigest()
        if raw != block.get("hash"):
            print(f"Invalid hash at block {i}")
            return False
        
        # เช็ค PoW (hash ต้องขึ้นต้นด้วย 0000)
        if not block.get("hash", "").startswith("0000"):
            print(f"Invalid PoW at block {i}")
            return False
    
    return True

def auto_sync_loop():
    import time
    import requests as _req
    time.sleep(15)  # รอให้ node start ก่อน
    while True:
        try:
            longest = node.chain
            for peer in list(node.peers):
                try:
                    r = _req.get(f"{peer}/chain", timeout=5)
                    peer_chain = r.json()
                    if validate_chain(peer_chain):
                        peer_work = sum(16 ** (64 - len(b.get("hash","").lstrip("0"))) for b in peer_chain)
                        cur_work = sum(16 ** (64 - len(b.get("hash","").lstrip("0"))) for b in longest)
                        if peer_work > cur_work:
                            longest = peer_chain
                            print(f"Found higher work chain from {peer}: {len(peer_chain)} blocks")
                except:
                    pass
            if len(longest) > len(node.chain):
                node.chain = longest
                node.save_chain()
                print(f"Auto-synced to {len(node.chain)} blocks")
        except Exception as e:
            print(f"Auto-sync error: {e}")
        time.sleep(30)

threading.Thread(target=auto_sync_loop, daemon=True).start()
print("Auto-sync thread started")

app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 6002)))

