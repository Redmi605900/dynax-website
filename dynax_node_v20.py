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
        self._load_initial_peers()
        self.CHAIN_FILE = "dynax_chain.json"
        self.load_chain()

    def _load_initial_peers(self):
        try:
            import json as _j
            peers = _j.load(open("peers.json"))
            for p in peers:
                self.peers.add(p)
            print(f"Loaded {len(peers)} peers from peers.json")
        except:
            pass

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
        clean_mempool()
        txs_pending = self.mempool[:50]
        total_fees = calc_total_fees(txs_pending)
        reward = {"from": "SYSTEM", "to": miner, "amount": 50 + total_fees, "fee": 0, "timestamp": int(time.time())}
        clean_mempool()
        txs = self.mempool[:50]
        self.mempool = self.mempool[50:]
        prev_hash = self.chain[-1]["hash"] if self.chain else "0"*64
        block = {"index": len(self.chain), "timestamp": int(time.time()), "transactions": [reward] + txs, "prev_hash": prev_hash, "nonce": 0}
        while True:
            raw = json.dumps(block, sort_keys=True)
            h = hashlib.sha3_256(raw.encode()).hexdigest()
            difficulty = get_difficulty(self.chain)
            if h.startswith(difficulty):
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
    fee = float(data.get('fee', 0.01))
    min_fee = get_min_fee()
    if fee < min_fee:
        return jsonify({"error": f"Fee too low. Minimum: {min_fee} DYX"}), 400
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



@app.route("/snapshot")
def snapshot():
    chainwork = 0
    for b in node.chain:
        h = b.get("hash","")
        zeros = len(h) - len(h.lstrip("0"))
        chainwork += 16 ** zeros

    return jsonify({
        "height": len(node.chain),
        "chainwork": chainwork,
        "blocks": node.chain,
        "peers": list(node.peers)
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
    # ตรวจ signature ทุก tx ใน block
    for tx in block.get("transactions", []):
        if not verify_tx_signature(tx):
            return jsonify({"error": "invalid tx signature"}), 400
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
    print(f"DEBUG: starting sync, own chain length={len(longest)}, peers={node.peers}")
    for peer in node.peers:
        try:
            r = requests.get(f"{peer}/chain", timeout=10)
            peer_chain = r.json()
            print(f"DEBUG: got {len(peer_chain)} blocks from {peer}")
            if len(peer_chain) > len(longest):
                longest = peer_chain
                print(f"DEBUG: {peer} is now the longest with {len(longest)} blocks")
        except Exception as e:
            print(f"Sync error from {peer}: {e}")
    print(f"DEBUG: final longest before reorg={len(longest)}")
    result = reorg_chain(longest)
    print(f"DEBUG: reorg_chain returned {result}")
    if result:
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
        "https://dynax-node2.onrender.com",
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
    """คำนวณ pool state จาก chain"""
    pool = {"DYX": 100000, "USDT": 50000}
    for block in node.chain:
        for tx in block.get("transactions", []):
            if tx.get("type") == "dex_swap":
                pool[tx["token_in"]] = pool.get(tx["token_in"], 0) + tx["amount_in"]
                pool[tx["token_out"]] = pool.get(tx["token_out"], 0) - tx["amount_out"]
            elif tx.get("type") == "dex_liquidity":
                pool[tx["token"]] = pool.get(tx["token"], 0) + tx["amount"]
    return pool

def save_pool(pool):
    with open(POOL_FILE, "w") as f:
        _json.dump(pool, f)

def get_pool():
    """ดึง pool state ล่าสุดจาก chain"""
    return load_pool()

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
        pool = get_pool()
        pool[token] = pool.get(token, 0) + amount
        
        liq_tx = {
            "type": "dex_liquidity",
            "token": token,
            "amount": amount,
            "timestamp": int(__import__("time").time()),
            "from": "DEX",
            "to": "DEX"
        }
        node.mempool.append(liq_tx)
        save_pool(pool)
        liquidity_pool.update(pool)
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
    if is_duplicate_tx(tx):
        return jsonify({"status": "already have tx"})
    node.mempool.append(tx)
    # relay ต่อไปยัง peer อื่น
    threading.Thread(target=broadcast_tx, args=(tx,), daemon=True).start()
    return jsonify({"status": "received", "mempool_size": len(node.mempool)})


def get_difficulty(chain):
    """คำนวณ difficulty จาก block time เฉลี่ย"""
    TARGET_BLOCK_TIME = 12  # วินาที
    ADJUST_EVERY = 10  # ปรับทุก 10 blocks
    MIN_DIFF = 3  # ขั้นต่ำ 3 zeros
    MAX_DIFF = 6  # สูงสุด 6 zeros
    
    if len(chain) < ADJUST_EVERY + 1:
        return "0000"  # default 4 zeros
    
    # เอา 10 blocks ล่าสุด
    recent = chain[-ADJUST_EVERY:]
    time_taken = recent[-1]["timestamp"] - recent[0]["timestamp"]
    
    if time_taken <= 0:
        return "0000"
    
    avg_time = time_taken / (ADJUST_EVERY - 1)
    current_zeros = len("0000")  # เริ่มจาก 4
    
    # ปรับ difficulty
    if avg_time < TARGET_BLOCK_TIME * 0.5:
        # เร็วเกินไป → เพิ่ม difficulty
        new_zeros = min(current_zeros + 1, MAX_DIFF)
    elif avg_time > TARGET_BLOCK_TIME * 2:
        # ช้าเกินไป → ลด difficulty
        new_zeros = max(current_zeros - 1, MIN_DIFF)
    else:
        new_zeros = current_zeros
    
    return "0" * new_zeros



def get_nonce(addr):
    """นับจำนวน tx ที่ส่งจาก address นี้"""
    count = 0
    for block in node.chain:
        for tx in block.get("transactions", []):
            if tx.get("from") == addr:
                count += 1
    return count

def check_replay(tx):
    """ตรวจสอบ replay attack - tx เดิมส่งซ้ำ"""
    sig = tx.get("signature")
    if not sig:
        return False
    for block in node.chain:
        for t in block.get("transactions", []):
            if t.get("signature") == sig:
                return True
    return False


def calc_cumulative_work(chain):
    """คำนวณ cumulative work ของ chain"""
    total = 0
    for block in chain:
        h = block.get("hash", "")
        zeros = len(h) - len(h.lstrip("0"))
        total += 16 ** zeros
    return total

def reorg_chain(new_chain):
    """เปลี่ยน chain ถ้า new_chain มี cumulative work มากกว่า"""
    if not validate_chain(new_chain):
        return False
    new_work = calc_cumulative_work(new_chain)
    cur_work = calc_cumulative_work(node.chain)
    if new_work > cur_work:
        print(f"Reorg: {len(node.chain)} -> {len(new_chain)} blocks")
        node.chain = new_chain
        node.save_chain()
        # คืน tx ที่ถูก orphan กลับ mempool
        confirmed = set()
        for block in new_chain:
            for tx in block.get("transactions", []):
                confirmed.add(tx.get("signature",""))
        for block in node.chain:
            for tx in block.get("transactions", []):
                sig = tx.get("signature","")
                if sig and sig not in confirmed:
                    node.mempool.append(tx)
        return True
    return False



def verify_tx_signature(tx):
    """ตรวจสอบ signature ของ transaction"""
    try:
        from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
        import hashlib as _hl
        
        sender = tx.get("from")
        if sender in ("SYSTEM", "GENESIS", "DEX"):
            return True
            
        signature = tx.get("signature")
        if not signature:
            return False
            
        # หา public key จาก chain
        pub_hex = None
        for block in node.chain:
            for t in block.get("transactions", []):
                if t.get("from") == sender and t.get("public_key"):
                    pub_hex = t["public_key"]
                    break
                    
        if not pub_hex:
            return True  # ยังไม่มี tx เก่า ผ่านไปก่อน
            
        msg = _hl.sha3_256(
            __import__("json").dumps(
                {"amount": tx["amount"], "fee": tx.get("fee",0), 
                 "from": tx["from"], "to": tx["to"]}, 
                sort_keys=True, separators=(",",":")
            ).encode()
        ).digest()
        
        vk = VerifyingKey.from_string(bytes.fromhex(pub_hex), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature), msg)
        return True
    except:
        return False

def calc_total_fees(txs):
    """คำนวณ fee รวมจาก transactions"""
    return sum(float(tx.get("fee", 0)) for tx in txs if tx.get("from") != "SYSTEM")

def get_min_fee():
    """คำนวณ minimum fee จาก mempool"""
    if len(node.mempool) < 100:
        return 0.01  # mempool ยังว่าง fee ขั้นต่ำปกติ
    fees = sorted([float(tx.get("fee", 0)) for tx in node.mempool])
    return fees[len(fees)//2]  # median fee

def clean_mempool():
    """ลบ tx ซ้ำและจัดลำดับตาม fee"""
    seen = set()
    unique = []
    for tx in node.mempool:
        sig = tx.get("signature", str(tx.get("timestamp","")))
        if sig not in seen:
            seen.add(sig)
            unique.append(tx)
    # เรียงตาม fee มากไปน้อย
    unique.sort(key=lambda x: float(x.get("fee", 0)), reverse=True)
    # จำกัด 1000 tx
    node.mempool = unique[:1000]

def is_duplicate_tx(tx):
    """ตรวจว่า tx อยู่ใน mempool หรือ chain แล้วไหม"""
    sig = tx.get("signature")
    if not sig:
        return False
    # เช็ค mempool
    for m in node.mempool:
        if m.get("signature") == sig:
            return True
    # เช็ค chain
    for block in node.chain:
        for t in block.get("transactions", []):
            if t.get("signature") == sig:
                return True
    return False

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
        expected_diff = get_difficulty(chain[:i])
        # ตรวจ difficulty ใน block ต้องตรงกับที่คำนวณได้
        if block.get("difficulty") and block["difficulty"] != expected_diff:
            print(f"Invalid difficulty at block {i}: expected {expected_diff} got {block['difficulty']}")
            return False
        # ตรวจ hash ต้องผ่าน PoW ตาม expected difficulty
        if not block.get("hash", "").startswith(expected_diff):
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
            if reorg_chain(longest):
                print(f"Auto-synced/reorged to {len(node.chain)} blocks")
        except Exception as e:
            print(f"Auto-sync error: {e}")
        time.sleep(30)

threading.Thread(target=auto_sync_loop, daemon=True).start()
PEERS_FILE = "peers.json"
MAX_PEERS = 100
MAX_NEW_PEERS_PER_ROUND = 10
MAX_FAILURES = 5
peer_lock = threading.Lock()
peer_failures = {}

def save_peers():
    try:
        import json as _j
        with peer_lock:
            _j.dump(list(node.peers), open(PEERS_FILE, "w"))
    except: pass

def load_peers():
    try:
        import json as _j
        peers = _j.load(open(PEERS_FILE))
        for p in peers:
            node.peers.add(p)
        print(f"Loaded {len(peers)} peers")
    except: pass

def is_valid_peer(url):
    if not url: return False
    if not (url.startswith("http://") or url.startswith("https://")): return False
    if len(url) > 200: return False
    return True

def verify_peer(url):
    import requests as _req
    try:
        r = _req.get(f"{url}/api/v1/info", timeout=5)
        data = r.json()
        return (data.get("network_id") == 1337 and data.get("network") == "DYNAX")
    except: return False

def remove_dead_peers():
    import requests as _req
    to_remove = []
    with peer_lock:
        peers_copy = list(node.peers)
    for peer in peers_copy:
        try:
            _req.get(f"{peer}/stats", timeout=3)
            peer_failures[peer] = 0
        except:
            peer_failures[peer] = peer_failures.get(peer, 0) + 1
            if peer_failures[peer] >= MAX_FAILURES:
                to_remove.append(peer)
    for peer in to_remove:
        with peer_lock:
            node.peers.discard(peer)
        print(f"Removed dead peer: {peer}")

def peer_discovery_loop():
    import time
    import requests as _req
    load_peers()
    time.sleep(20)
    my_url = os.environ.get("MY_URL", "")
    while True:
        try:
            new_peers = set()
            with peer_lock:
                peers_copy = list(node.peers)
            for peer in peers_copy:
                try:
                    r = _req.get(f"{peer}/peers", timeout=5)
                    data = r.json()
                    for p in data.get("peers", []):
                        if (p and p != my_url and p not in node.peers
                                and is_valid_peer(p) and len(node.peers) < MAX_PEERS):
                            new_peers.add(p)
                except: pass
            added = 0
            for p in list(new_peers)[:MAX_NEW_PEERS_PER_ROUND]:
                if verify_peer(p):
                    with peer_lock:
                        node.peers.add(p)
                    added += 1
                    print(f"Discovered: {p}")
            remove_dead_peers()
            save_peers()
        except Exception as e:
            print(f"Peer discovery error: {e}")
        time.sleep(60)

threading.Thread(target=peer_discovery_loop, daemon=True).start()
print("Peer discovery started")

print("Auto-sync thread started")


import hashlib as _hl
import json as _json

def get_chain_hash(chain):
    """คำนวณ hash ของ chain ทั้งหมดสำหรับ verify"""
    data = _json.dumps([b.get("hash","") for b in chain], separators=(",",":"))
    return _hl.sha3_256(data.encode()).hexdigest()

@app.route("/snapshot")
def get_snapshot():
    """ส่ง chain snapshot สำหรับ node ใหม่"""
    chain = node.chain
    return _json.dumps({
        "height": len(chain),
        "chain_hash": get_chain_hash(chain),
        "chain": chain,
        "network_id": 1337,
        "symbol": "DYX"
    }), 200, {"Content-Type": "application/json"}

@app.route("/snapshot/info")
def snapshot_info():
    """ข้อมูล snapshot โดยไม่ต้อง download chain"""
    return jsonify({
        "height": len(node.chain),
        "chain_hash": get_chain_hash(node.chain),
        "network_id": 1337,
        "peers": list(node.peers)
    })

def sync_from_snapshot(peer_url):
    """โหลด chain จาก snapshot ของ peer"""
    import requests as _req
    try:
        print(f"Downloading snapshot from {peer_url}...")
        r = _req.get(f"{peer_url}/snapshot", timeout=60)
        data = r.json()
        
        # ตรวจสอบ network_id
        if data.get("network_id") != 1337:
            print("Wrong network_id!")
            return False
            
        chain = data.get("chain", [])
        chain_hash = data.get("chain_hash")
        
        # verify chain hash
        if get_chain_hash(chain) != chain_hash:
            print("Chain hash mismatch!")
            return False
            
        # validate chain
        if not validate_chain(chain):
            print("Invalid chain!")
            return False
            
        # เปรียบเทียบ cumulative work
        if calc_cumulative_work(chain) > calc_cumulative_work(node.chain):
            node.chain = chain
            node.save_chain()
            print(f"Snapshot synced! Height: {len(chain)}")
            return True
        else:
            print("Current chain has more work")
            return False
    except Exception as e:
        print(f"Snapshot sync error: {e}")
        return False

def initial_snapshot_sync():
    """sync chain จาก snapshot ตอน node เริ่มต้น"""
    import time
    time.sleep(5)
    static_peers = [
        "https://web-production-8bbb8.up.railway.app",
        "https://dynax-node2.onrender.com",
        "https://dynax-node.onrender.com"
    ]
    for peer in static_peers:
        try:
            r = __import__("requests").get(f"{peer}/snapshot/info", timeout=5)
            info = r.json()
            if info.get("height", 0) > len(node.chain):
                if sync_from_snapshot(peer):
                    print(f"Initial sync from {peer} complete!")
                    break
        except:
            pass

#threading.Thread(target=initial_snapshot_sync, daemon=True).start()
print("Snapshot sync disabled temporarily")


def sync_mempool_from_peers():
    """ดึง mempool จากทุก peer"""
    import requests as _req
    for peer in list(node.peers):
        try:
            r = _req.get(f"{peer}/pending", timeout=5)
            data = r.json()
            txs = data.get("transactions", [])
            added = 0
            for tx in txs:
                if not is_duplicate_tx(tx) and not check_replay(tx):
                    node.mempool.append(tx)
                    added += 1
            if added > 0:
                print(f"Mempool sync: +{added} tx from {peer}")
        except:
            pass
    clean_mempool()

def mempool_sync_loop():
    """sync mempool ทุก 15 วินาที"""
    import time
    time.sleep(25)
    while True:
        try:
            sync_mempool_from_peers()
        except Exception as e:
            print(f"Mempool sync error: {e}")
        time.sleep(15)

threading.Thread(target=mempool_sync_loop, daemon=True).start()
print("Mempool sync started")


def reconstruct_state():
    """คำนวณ state ทั้งหมดจาก chain ล้วนๆ"""
    state = {
        "balances": {},
        "dex_pool": {"DYX": 100000, "USDT": 50000},
        "total_supply": 0,
        "tx_count": 0,
        "nonces": {}
    }
    
    for block in node.chain:
        for tx in block.get("transactions", []):
            sender = tx.get("from", "")
            receiver = tx.get("to", "")
            amount = float(tx.get("amount", 0))
            fee = float(tx.get("fee", 0))
            tx_type = tx.get("type", "transfer")
            
            if tx_type == "dex_swap":
                token_in = tx.get("token_in")
                token_out = tx.get("token_out")
                amt_in = float(tx.get("amount_in", 0))
                amt_out = float(tx.get("amount_out", 0))
                if token_in and token_out:
                    state["dex_pool"][token_in] = state["dex_pool"].get(token_in, 0) + amt_in
                    state["dex_pool"][token_out] = state["dex_pool"].get(token_out, 0) - amt_out
                    
            elif tx_type == "dex_liquidity":
                token = tx.get("token")
                amt = float(tx.get("amount", 0))
                if token:
                    state["dex_pool"][token] = state["dex_pool"].get(token, 0) + amt
                    
            else:
                # transfer ปกติ
                if sender == "SYSTEM" or sender == "GENESIS":
                    state["balances"][receiver] = state["balances"].get(receiver, 0) + amount
                    state["total_supply"] += amount
                elif sender:
                    state["balances"][sender] = state["balances"].get(sender, 0) - amount - fee
                    state["balances"][receiver] = state["balances"].get(receiver, 0) + amount
                    state["nonces"][sender] = state["nonces"].get(sender, 0) + 1
                    
            state["tx_count"] += 1
    
    return state

@app.route("/state")
def get_state():
    """ดึง state ปัจจุบันที่ derive จาก chain"""
    state = reconstruct_state()
    return jsonify({
        "total_supply": state["total_supply"],
        "tx_count": state["tx_count"],
        "dex_pool": state["dex_pool"],
        "block_height": len(node.chain),
        "status": "reconstructed_from_chain"
    })

@app.route("/state/balance/<addr>")
def state_balance(addr):
    """ดึง balance จาก state reconstruction"""
    state = reconstruct_state()
    return jsonify({
        "address": addr,
        "balance": state["balances"].get(addr, 0),
        "nonce": state["nonces"].get(addr, 0),
        "source": "chain_reconstruction"
    })



import hmac as _hmac
import hashlib as _hl2
import time as _time2

P2P_SECRET = os.environ.get("P2P_SECRET", "dynax_network_1337")

def sign_p2p_message(data):
    """สร้าง signature สำหรับ P2P message"""
    timestamp = int(_time2.time())
    payload = f"{timestamp}:{data}"
    sig = _hmac.new(
        P2P_SECRET.encode(),
        payload.encode(),
        _hl2.sha256
    ).hexdigest()
    return {"timestamp": timestamp, "signature": sig}

def verify_p2p_message(timestamp, signature, data):
    """ตรวจสอบ P2P message"""
    # ตรวจ timestamp ไม่เกิน 60 วินาที
    if abs(int(_time2.time()) - int(timestamp)) > 60:
        return False
    payload = f"{timestamp}:{data}"
    expected = _hmac.new(
        P2P_SECRET.encode(),
        payload.encode(),
        _hl2.sha256
    ).hexdigest()
    return _hmac.compare_digest(signature, expected)

@app.route("/p2p/verify", methods=["POST"])
def p2p_verify():
    """ตรวจสอบว่า node นี้เป็น DYNAX node จริง"""
    data = request.json
    timestamp = data.get("timestamp")
    signature = data.get("signature")
    challenge = data.get("challenge", "")
    
    if verify_p2p_message(timestamp, signature, challenge):
        return jsonify({
            "verified": True,
            "network_id": 1337,
            "node": "DYNAX v20"
        })
    return jsonify({"verified": False}), 401

def broadcast_block_signed(block):
    """ส่ง block พร้อม P2P signature"""
    import requests as _req
    block_data = __import__("json").dumps(block, sort_keys=True)
    auth = sign_p2p_message(block_data[:64])
    
    for peer in list(node.peers):
        try:
            _req.post(f"{peer}/receive_block", 
                json={**block, "_p2p_ts": auth["timestamp"], "_p2p_sig": auth["signature"]},
                timeout=5)
        except:
            pass


app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 6002)))



def download_snapshot(peer):
    try:
        r = requests.get(f"{peer}/snapshot", timeout=20)
        data = r.json()

        if data["height"] > len(node.chain):
            node.chain = data["blocks"]
            node.peers.update(data.get("peers", []))
            node.save_chain()
            print(f"Snapshot synced: {len(node.chain)} blocks")

    except Exception as e:
        print("Snapshot sync failed:", e)


