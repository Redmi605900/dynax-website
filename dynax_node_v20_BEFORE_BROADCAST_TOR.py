import time
import requests
import threading

# ===== Tor .onion peer support =====
_TOR_PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

def peer_request(method, url, **kwargs):
    """
    Wrapper รอบ requests ที่รองรับทั้ง peer ปกติและ .onion peer
    .onion peer จะถูกส่งผ่าน Tor SOCKS proxy อัตโนมัติ
    peer ปกติทำงานเหมือนเดิมทุกประการ ไม่กระทบ
    """
    if '.onion' in url:
        kwargs.setdefault('proxies', _TOR_PROXIES)
        kwargs.setdefault('timeout', 60)
    return getattr(requests, method)(url, **kwargs)

import json
import hashlib
import os
from flask import Flask, jsonify, request
from ecdsa import VerifyingKey, SECP256k1

app = Flask(__name__)

# ===== DYNAX CONSENSUS V1 =====
# Historical blocks 0..10207 are preserved as legacy history.
# Consensus V1 starts at block 10208.
CONSENSUS_V1_HEIGHT = 10208
CONSENSUS_V1_POW_PREFIX = "0000"
CONSENSUS_V1_NETWORK_ID = 1337
CONSENSUS_V1_SYMBOL = "DYX"

def calculate_block_hash(block):
    """Canonical SHA3-256 hash of a block, excluding the stored hash field."""
    raw = {
        k: v for k, v in block.items()
        if k != "hash"
    }
    return hashlib.sha3_256(
        json.dumps(raw, sort_keys=True).encode()
    ).hexdigest()

def validate_block_pow(block, required_prefix=CONSENSUS_V1_POW_PREFIX):
    """Verify canonical block hash and Consensus V1 proof-of-work."""
    calculated = calculate_block_hash(block)
    stored = block.get("hash", "")

    if calculated != stored:
        return False

    if not stored.startswith(required_prefix):
        return False

    return True

# ===== DYNAX CONSENSUS V2 (difficulty retarget + timestamp rules) =====
# Applies to blocks with index >= CONSENSUS_V2_HEIGHT. Earlier blocks keep V1/legacy rules.
CONSENSUS_V2_HEIGHT = 10210
V2_INITIAL_TARGET = 1 << 240   # same hardness as the old "0000" prefix
V2_MAX_TARGET = 1 << 248       # easiest allowed target
V2_TARGET_SPACING = 12         # seconds per block
V2_ADJUST_INTERVAL = 10        # retarget every N blocks
V2_MAX_ADJUST = 4              # max change factor per retarget
V2_MTP_WINDOW = 11
V2_MAX_FUTURE_SECONDS = 180

def expected_target_v2(chain_prefix):
    i = len(chain_prefix)
    if i <= CONSENSUS_V2_HEIGHT:
        return V2_INITIAL_TARGET
    prev_target = int(chain_prefix[-1]["target"], 16)
    if (i - CONSENSUS_V2_HEIGHT) % V2_ADJUST_INTERVAL != 0:
        return prev_target
    window = chain_prefix[i - V2_ADJUST_INTERVAL:i]
    expected = V2_TARGET_SPACING * (V2_ADJUST_INTERVAL - 1)
    actual = window[-1]["timestamp"] - window[0]["timestamp"]
    actual = max(expected // V2_MAX_ADJUST, min(expected * V2_MAX_ADJUST, actual))
    return max(1, min(V2_MAX_TARGET, prev_target * actual // expected))

def validate_block_pow_v2(block, chain_prefix):
    try:
        if calculate_block_hash(block) != block.get("hash", ""):
            return False
        target = expected_target_v2(chain_prefix)
        if block.get("target") != "%064x" % target:
            return False
        return int(block["hash"], 16) < target
    except Exception:
        return False

def validate_block_pow_ctx(block, chain_prefix):
    if block.get("index", -1) >= CONSENSUS_V2_HEIGHT:
        return validate_block_pow_v2(block, chain_prefix)
    return validate_block_pow(block)

def validate_block_time_v2(block, chain_prefix, check_future=False):
    import time as _t
    try:
        ts = block.get("timestamp")
        if not isinstance(ts, int) or isinstance(ts, bool):
            return False
        times = sorted(int(b.get("timestamp", 0)) for b in chain_prefix[-V2_MTP_WINDOW:])
        if ts <= times[len(times) // 2]:
            return False
        if check_future and ts > int(_t.time()) + V2_MAX_FUTURE_SECONDS:
            return False
        return True
    except Exception:
        return False

# ===== END DYNAX CONSENSUS V1 =====

# ===== Categorized Logging =====
import sys as _sys
import os as _os
from datetime import datetime as _dt

_os.makedirs("logs", exist_ok=True)

class _CategorizedLogger:
    def __init__(self, original):
        self.original = original
        self.files = {
            "error": open("logs/error.log", "a", buffering=1),
            "mining": open("logs/mining.log", "a", buffering=1),
            "network": open("logs/network.log", "a", buffering=1),
            "general": open("logs/general.log", "a", buffering=1),
        }

    def _categorize(self, msg):
        m = msg.lower()
        if any(k in m for k in ["error", "traceback", "exception", "invalid", "reject", "fail"]):
            return "error"
        if any(k in m for k in ["mine", "auto-mine", "mining", "block reward"]):
            return "mining"
        if any(k in m for k in ["peer", "sync", "broadcast", "connect", "tunnel"]):
            return "network"
        return "general"

    def write(self, message):
        self.original.write(message)
        if message.strip():
            ts = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            cat = self._categorize(message)
            self.files[cat].write(f"{ts} - {message}" + ("\n" if not message.endswith("\n") else ""))

    def flush(self):
        self.original.flush()
        for f in self.files.values():
            f.flush()

_sys.stdout = _CategorizedLogger(_sys.stdout)
# ===== End Categorized Logging =====


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

            # Never load this node's own URL as a peer.
            port = int(os.environ.get("PORT", 6001))
            my_url = os.environ.get("MY_URL", "").strip()
            if not my_url:
                my_url = f"http://127.0.0.1:{port}"

            loaded = 0
            skipped_self = 0

            for p in peers:
                p = str(p).strip().rstrip("/")
                if not p:
                    continue

                if p.rstrip("/") == my_url.rstrip("/"):
                    skipped_self += 1
                    continue

                self.peers.add(p)
                loaded += 1

            print(
                f"Loaded {loaded} peers from peers.json "
                f"(skipped self: {skipped_self})"
            )
        except Exception as e:
            print(f"Initial peer load error: {e}")

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
                if tx.get("from") == addr: bal -= tx.get("amount", 0) + tx.get("fee", 0)
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

        MAX_SUPPLY = 11000000
        BLOCK_REWARD = 1
        total_mined = sum(
            tx.get("amount", 0)
            for block in self.chain
            for tx in block.get("transactions", [])
            if tx.get("from") == "SYSTEM"
        )
        block_reward = BLOCK_REWARD
        if total_mined + block_reward > MAX_SUPPLY:
            block_reward = max(0, MAX_SUPPLY - total_mined)
        if block_reward == 0 and total_fees == 0:
            return {"error": "max supply reached"}

        reward = {"from": "SYSTEM", "to": miner, "amount": block_reward + total_fees, "fee": 0, "timestamp": int(time.time())}
        clean_mempool()
        txs = self.mempool[:50]
        # Do NOT remove selected mempool transactions yet.
        # They are committed only after the block passes all local
        # consensus/state validation and is persisted successfully.
        prev_hash = self.chain[-1]["hash"] if self.chain else "0"*64
        block = {"index": len(self.chain), "timestamp": int(time.time()), "transactions": [reward] + txs, "prev_hash": prev_hash, "nonce": 0}
        _v2_target = None
        if len(self.chain) >= CONSENSUS_V2_HEIGHT:
            _v2_target = expected_target_v2(self.chain)
            block["target"] = "%064x" % _v2_target
        while True:
            raw = json.dumps(block, sort_keys=True)
            h = hashlib.sha3_256(raw.encode()).hexdigest()
            # ===== Consensus V1 mining rule =====
            # Legacy blocks keep the historical difficulty logic.
            # Block 10208 onward uses the fixed Consensus V1 target.
            if _v2_target is not None:
                _pow_ok = int(h, 16) < _v2_target
            else:
                if len(self.chain) >= CONSENSUS_V1_HEIGHT:
                    difficulty = CONSENSUS_V1_POW_PREFIX
                else:
                    difficulty = get_difficulty(self.chain)
                _pow_ok = h.startswith(difficulty)

            if _pow_ok:
                block["hash"] = h
                break
            block["nonce"] += 1
        # ===== Consensus V1 local self-validation =====
        # Never commit a mined block before applying the same
        # core validation rules used for received blocks.
        if block["index"] >= CONSENSUS_V1_HEIGHT:
            if block.get("index") != len(self.chain):
                return {"error": "local validation: invalid index"}

            if self.chain and block.get("prev_hash") != self.chain[-1].get("hash"):
                return {"error": "local validation: invalid prev_hash"}

            if not validate_block_pow_ctx(block, self.chain):
                return {"error": "local validation: invalid hash or proof-of-work"}

            if block["index"] >= CONSENSUS_V2_HEIGHT and not validate_block_time_v2(block, self.chain, check_future=True):
                return {"error": "local validation: invalid block timestamp"}

        for tx in block.get("transactions", []):
            if not verify_tx_signature(tx):
                return {"error": "local validation: invalid tx signature"}

        if not validate_block_balances(block, self.chain):
            return {"error": "local validation: insufficient balance in block"}

        self.chain.append(block)
        self.save_chain()

        # Commit only the transactions actually included in the block.
        # If any local validation above fails, the mempool is untouched.
        committed_signatures = {
            tx.get("signature")
            for tx in txs
            if tx.get("signature")
        }
        if committed_signatures:
            self.mempool = [
                tx for tx in self.mempool
                if tx.get("signature") not in committed_signatures
            ]

        print(f"Block {block['index']} mined successfully with nonce {block['nonce']}")
        
        # Broadcast new block to all peers
        for peer in list(self.peers):
            try:
                r = peer_request("post", f"{peer}/receive_block", json=block, timeout=3)
                print(f"Broadcasted block {block['index']} to {peer}: {r.status_code}")
            except Exception as e:
                print(f"Failed to broadcast to {peer}: {e}")
        
        return {"status": "mined", "block": block["index"]}

node = DynaxNode()

@app.route("/tx", methods=["POST"])
def tx():
    data = request.get_json() or {}

    required = ["from", "to", "amount", "signature", "public_key"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing fields"}), 400

    try:
        amount = float(data["amount"])
        fee = float(data.get("fee", 0.01))
    except (TypeError, ValueError):
        return jsonify({"error": "amount หรือ fee ไม่ถูกต้อง"}), 400

    tx_data = {
        "from": data["from"],
        "to": data["to"],
        "amount": amount,
        "fee": fee,
        "signature": data["signature"],
        "public_key": data["public_key"],
        "timestamp": int(data.get("timestamp", time.time()))
    }

    if amount <= 0:
        return jsonify({"error": "invalid amount"}), 400

    if fee < 0:
        return jsonify({"error": "invalid fee"}), 400

    min_fee = get_min_fee()
    if fee < min_fee:
        return jsonify({"error": f"Fee too low. Minimum: {min_fee} DYX"}), 400

    if node.balance(tx_data["from"]) < amount + fee:
        return jsonify({"error": "insufficient balance"}), 400

    if is_duplicate_tx(tx_data):
        return jsonify({"error": "duplicate transaction"}), 400

    if check_replay(tx_data):
        return jsonify({"error": "replay transaction"}), 400

    if not verify_tx_signature(tx_data):
        return jsonify({"error": "invalid signature"}), 400

    node.mempool.append(tx_data)

    return jsonify({
        "message": "Transaction added to mempool",
        "mempool_size": len(node.mempool),
        "tx": tx_data
    }), 201

@app.route("/chain")
def get_chain(): return jsonify(node.chain)

@app.route("/balance/<addr>")
def balance(addr): return jsonify({"address": addr, "balance": node.balance(addr)})

@app.route("/mine/<miner>")
def mine(miner):
    import hmac as _hm
    _tok = os.environ.get("MINE_TOKEN", "")
    if not _tok or not _hm.compare_digest(request.headers.get("X-Mine-Token", ""), _tok):
        return jsonify({"error": "mining endpoint is private"}), 403
    return jsonify(node.mine(miner))

@app.route("/")
def home():
    try:
        return open("index.html", encoding="utf-8").read()
    except:
        return jsonify({"network": "DYNAX v20 Secure", "blocks": len(node.chain), "api_v1": True})

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

@app.route("/blocks/recent/<int:n>")
def get_recent_blocks(n):
    """คืนแค่ n blocks ล่าสุด เบากว่า /blocks ทั้งหมดมาก ใช้สำหรับ Explorer"""
    n = min(n, 100)  # จำกัดสูงสุด 100 กันโหลดหนักเกินไป
    return jsonify(node.chain[-n:] if len(node.chain) > n else node.chain)


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
    return jsonify({"error": "removed"}), 404



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

UNLOCK_ATTEMPTS = {}
UNLOCK_MAX_ATTEMPTS = 5
UNLOCK_WINDOW_SECONDS = 900

def check_rate_limit(ip):
    now = time.time()
    attempts = UNLOCK_ATTEMPTS.get(ip, [])
    attempts = [t for t in attempts if now - t < UNLOCK_WINDOW_SECONDS]
    UNLOCK_ATTEMPTS[ip] = attempts
    return len(attempts) < UNLOCK_MAX_ATTEMPTS

def record_attempt(ip):
    UNLOCK_ATTEMPTS.setdefault(ip, []).append(time.time())

@app.route("/wallet/unlock", methods=["POST"])
def wallet_unlock():
    return jsonify({"error": "server-side key custody is disabled; sign transactions client-side"}), 410
    ip = request.remote_addr
    if not check_rate_limit(ip):
        return jsonify({"error": "พยายามผิดพลาดหลายครั้งเกินไป กรุณารอ 15 นาที"}), 429

    data = request.json
    address = data.get('address')
    password = data.get('password')

    try:
        with open("wallets/wallet_encrypted.json", "r") as f:
            wallet = json.load(f)

        if wallet['address'] != address:
            record_attempt(ip)
            return jsonify({"error": "Address ไม่ตรงกัน"}), 400

        if not wallet.get('encrypted'):
            return jsonify({"error": "Wallet ไม่ได้ encrypt"}), 400

        private_key = decrypt_wallet(wallet['private_key_encrypted'], password)
        pubkey_bytes = bytes.fromhex(wallet['public_key'])
        derived_addr = pubkey_to_address(pubkey_bytes)
        if derived_addr.lower() != address.lower():
            record_attempt(ip)
            return jsonify({"error": "รหัสผ่านไม่ถูกต้อง"}), 401

        UNLOCK_ATTEMPTS[ip] = []
        return jsonify({
            "address": wallet['address'],
            "private_key": private_key
        })
    except Exception as e:
        record_attempt(ip)
        return jsonify({"error": "รหัสผ่านไม่ถูกต้อง"}), 401


@app.route("/tx/send", methods=["POST"])
def send_tx_with_key():
    """ส่งธุรกรรมโดยเซ็นด้วย private_key และตรวจสอบ TX ก่อนเข้า mempool"""
    return jsonify({"error": "sending raw private keys to the server is disabled; sign transactions client-side and POST to /tx"}), 410
    from ecdsa import SigningKey, SECP256k1

    data = request.json or {}
    from_addr = data.get("from")
    to_addr = data.get("to")
    amount = data.get("amount")
    private_key_hex = data.get("private_key")

    try:
        amount = float(amount)
        fee = float(data.get("fee", 0.01))
    except (TypeError, ValueError):
        return jsonify({"error": "amount หรือ fee ไม่ถูกต้อง"}), 400

    if not from_addr or not to_addr or not private_key_hex:
        return jsonify({"error": "ข้อมูลไม่ครบ"}), 400

    if amount <= 0:
        return jsonify({"error": "invalid amount"}), 400

    if fee < 0:
        return jsonify({"error": "invalid fee"}), 400

    min_fee = get_min_fee()
    if fee < min_fee:
        return jsonify({"error": f"Fee too low. Minimum: {min_fee} DYX"}), 400

    if node.balance(from_addr) < amount + fee:
        return jsonify({"error": "insufficient balance"}), 400

    try:
        # โหลด private key
        sk = SigningKey.from_string(
            bytes.fromhex(private_key_hex),
            curve=SECP256k1
        )

        # derive public key จาก private key
        pubkey_bytes = sk.get_verifying_key().to_string()
        public_key_hex = pubkey_bytes.hex()

        # ตรวจว่า private key นี้เป็นของ from address จริง
        derived_addr = pubkey_to_address(pubkey_bytes)
        if derived_addr.lower() != from_addr.lower():
            return jsonify({"error": "private key does not match from address"}), 400

        # canonical transaction message
        msg_dict = {
            "amount": amount,
            "fee": fee,
            "from": from_addr,
            "to": to_addr
        }

        msg_text = json.dumps(
            msg_dict,
            sort_keys=True,
            separators=(",", ":")
        )

        msg_hash = hashlib.sha3_256(msg_text.encode()).digest()
        signature = sk.sign_digest(msg_hash).hex()

        # transaction สำหรับ Consensus V1
        tx = {
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "fee": fee,
            "signature": signature,
            "public_key": public_key_hex,
            "timestamp": int(time.time())
        }

        # ตรวจ signature ซ้ำด้วย validator ตัวเดียวกับ Consensus V1
        if not verify_tx_signature(tx):
            return jsonify({"error": "invalid signature"}), 400

        # เพิ่มเข้า mempool หลังผ่าน validation ทั้งหมด
        node.mempool.append(tx)

        return jsonify({
            "message": "Transaction added to mempool",
            "mempool_size": len(node.mempool),
            "tx": tx
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400
def get_faucet_total_sent():
    total = 0.0
    for block in node.chain:
        for tx in block.get("transactions", []):
            if tx.get("from") == "FAUCET":
                total += float(tx.get("amount", 0))
    for tx in node.mempool:
        if tx.get("from") == "FAUCET":
            total += float(tx.get("amount", 0))
    return total

FAUCET_ATTEMPTS = {}
FAUCET_ADDR_ATTEMPTS = {}
FAUCET_MAX_ATTEMPTS = 3
FAUCET_WINDOW_SECONDS = 3600
FAUCET_AMOUNT = 10
FAUCET_MAX_TOTAL = 10000
FAUCET_CLAIMED_ADDRESSES = set()

@app.route("/api/faucet", methods=["POST"])
def faucet_claim():
    ip = request.remote_addr
    now = time.time()

    data = request.json or {}
    address = data.get("address", "").strip()

    # Address-based limit: the meaningful check when every request
    # arrives from the same tunnel IP. Checked before the IP-based
    # limit so a malformed/missing address fails fast with a clear error.
    if address:
        addr_attempts = FAUCET_ADDR_ATTEMPTS.get(address, [])
        addr_attempts = [t for t in addr_attempts if now - t < FAUCET_WINDOW_SECONDS]
        if len(addr_attempts) >= FAUCET_MAX_ATTEMPTS:
            return jsonify({"error": "ที่อยู่นี้พยายามหลายครั้งเกินไป กรุณารอ 1 ชั่วโมง"}), 429
        FAUCET_ADDR_ATTEMPTS[address] = addr_attempts + [now]

    # IP-based limit: secondary layer, still useful once real client
    # IPs are visible (e.g. behind a Named Tunnel).
    attempts = FAUCET_ATTEMPTS.get(ip, [])
    attempts = [t for t in attempts if now - t < FAUCET_WINDOW_SECONDS]
    if len(attempts) >= FAUCET_MAX_ATTEMPTS:
        return jsonify({"error": "พยายามหลายครั้งเกินไป กรุณารอ 1 ชั่วโมง"}), 429
    FAUCET_ATTEMPTS[ip] = attempts + [now]

    if not address or not address.startswith("DX") or len(address) != 42:
        return jsonify({"error": "ที่อยู่ wallet ไม่ถูกต้อง"}), 400

    if address in FAUCET_CLAIMED_ADDRESSES:
        return jsonify({"error": "ที่อยู่นี้เคยขอรับแล้ว"}), 400

    for block in node.chain:
        for tx in block.get("transactions", []):
            if tx.get("from") == "FAUCET" and tx.get("to") == address:
                FAUCET_CLAIMED_ADDRESSES.add(address)
                return jsonify({"error": "ที่อยู่นี้เคยขอรับแล้ว"}), 400

    total_sent = get_faucet_total_sent()
    if total_sent + FAUCET_AMOUNT > FAUCET_MAX_TOTAL:
        return jsonify({"error": "Faucet หมดแล้ว"}), 400

    tx = {
        "from": "FAUCET",
        "to": address,
        "amount": FAUCET_AMOUNT,
        "fee": 0,
        "timestamp": int(time.time())
    }
    node.mempool.append(tx)
    FAUCET_CLAIMED_ADDRESSES.add(address)

    return jsonify({
        "status": "queued",
        "amount": FAUCET_AMOUNT,
        "total_sent": total_sent + FAUCET_AMOUNT,
        "remaining": FAUCET_MAX_TOTAL - (total_sent + FAUCET_AMOUNT)
    }), 201


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
        "reward": 1,
        "status": "online"
    })

@app.route("/health")
def health():
    chain = node.chain
    last_block_time = chain[-1].get("timestamp", 0) if chain else 0
    seconds_since_last_block = int(time.time()) - last_block_time if last_block_time else None

    peer_status = {}
    for peer in list(node.peers):
        try:
            r = peer_request("get", f"{peer}/", timeout=3)
            peer_status[peer] = "online" if r.status_code == 200 else f"error_{r.status_code}"
        except Exception:
            peer_status[peer] = "offline"

    peers_online = sum(1 for v in peer_status.values() if v == "online")

    issues = []
    if seconds_since_last_block is not None and seconds_since_last_block > 300:
        issues.append(f"No new block in {seconds_since_last_block}s (over 5 min)")
    if len(chain) == 0:
        issues.append("Chain is empty")
    if peers_online == 0 and len(node.peers) > 0:
        issues.append("No peers reachable")

    overall_status = "healthy" if not issues else "degraded"

    return jsonify({
        "status": overall_status,
        "issues": issues,
        "chain_length": len(chain),
        "mempool_size": len(node.mempool),
        "seconds_since_last_block": seconds_since_last_block,
        "peers_total": len(node.peers),
        "peers_online": peers_online,
        "peer_status": peer_status,
        "checked_at": int(time.time())
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
    if not is_valid_peer(peer):
        return jsonify({"error": "invalid peer"}), 400
    if not verify_peer(peer):
        return jsonify({"error": "peer verification failed"}), 400
    node.peers.add(peer)
    return jsonify({"status": "added", "peer": peer})

@app.route("/receive_block", methods=["POST"])
def receive_block():
    block = request.json

    if not isinstance(block, dict):
        return jsonify({"error": "invalid block"}), 400

    # ===== P2P authentication =====
    p2p_ts = block.get("_p2p_ts")
    p2p_sig = block.get("_p2p_sig")

    if p2p_ts is None or not p2p_sig:
        return jsonify({"error": "missing P2P authentication"}), 401

    # Verify the exact block payload used by broadcast_block_signed().
    block_data = __import__("json").dumps(
        {k: v for k, v in block.items()
         if k not in ("_p2p_ts", "_p2p_sig")},
        sort_keys=True
    )

    if not verify_p2p_message(p2p_ts, p2p_sig, block_data):
        return jsonify({"error": "invalid P2P authentication"}), 401

    # ===== Consensus V1: exact next block index =====
    expected_index = len(node.chain)

    if block.get("index") != expected_index:
        return jsonify({
            "error": "invalid index",
            "expected": expected_index,
            "received": block.get("index")
        }), 400

    # ===== Consensus V1: previous block linkage =====
    if node.chain and block.get("prev_hash") != node.chain[-1].get("hash"):
        return jsonify({"error": "invalid prev_hash"}), 400

    # ===== Consensus V1: block hash + proof-of-work =====
    # Legacy history 0..10207 is preserved.
    # V1 consensus starts at block 10208.
    if block.get("index", -1) >= CONSENSUS_V1_HEIGHT:
        if not validate_block_pow_ctx(block, node.chain):
            return jsonify({
                "error": "invalid block hash or proof-of-work"
            }), 400
        if block.get("index", -1) >= CONSENSUS_V2_HEIGHT and not validate_block_time_v2(block, node.chain, check_future=True):
            return jsonify({"error": "invalid block timestamp"}), 400

    # ===== Transaction signatures =====
    for tx in block.get("transactions", []):
        if not verify_tx_signature(tx):
            return jsonify({"error": "invalid tx signature"}), 400

    # ===== Balance / double-spend protection =====
    if not validate_block_balances(block, node.chain):
        return jsonify({"error": "insufficient balance in block"}), 400

    node.chain.append(block)
    update_pubkey_cache_from_block(block)
    node.save_chain()

    return jsonify({
        "status": "accepted",
        "block": block["index"]
    })

@app.route("/sync")
def sync_chain():
    import hmac as _hm
    _tok = os.environ.get("MINE_TOKEN", "")
    if not _tok or not _hm.compare_digest(request.headers.get("X-Mine-Token", ""), _tok):
        return jsonify({"error": "sync endpoint is private"}), 403
    longest = node.chain
    print(f"DEBUG: starting sync, own chain length={len(longest)}, peers={node.peers}")
    for peer in node.peers:
        try:
            r = peer_request("get", f"{peer}/chain", timeout=10)
            peer_chain = r.json()
            print(f"DEBUG: got {len(peer_chain)} blocks from {peer}")
            if len(peer_chain) > len(longest) and validate_chain(peer_chain):
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
    # No hard-coded bootstrap peers.
    # Optional bootstrap is supplied explicitly via BOOTSTRAP_NODE.
    static_peers = []
    for p in static_peers:
        node.peers.add(p)

    import time
    time.sleep(10)
    bootstrap = os.environ.get("BOOTSTRAP_NODE", "")
    if bootstrap:
        try:
            peer_request("post", f"{bootstrap}/peers/add", json={"peer": os.environ.get("MY_URL", "")}, timeout=5)
            node.peers.add(bootstrap)
            print(f"Connected to bootstrap: {bootstrap}")
        except Exception as e:
            print(f"Bootstrap connect failed: {e}")

import threading
def resilient_loop(func, name, *args, **kwargs):
    """รันฟังก์ชันแบบ infinite loop พร้อม auto-restart ถ้า error หรือหลุดออกมาเอง"""
    while True:
        try:
            func(*args, **kwargs)
            print(f"[AUTO-RESTART] {name} exited normally, restarting in 5s...")
        except Exception as e:
            print(f"[AUTO-RESTART] {name} crashed: {e}, restarting in 5s...")
        time.sleep(5)

def resilient_loop(func, name, *args, **kwargs):
    """รันฟังก์ชันแบบ infinite loop พร้อม auto-restart ถ้า error หรือหลุดออกมาเอง"""
    while True:
        try:
            func(*args, **kwargs)
            print(f"[AUTO-RESTART] {name} exited normally, restarting in 5s...")
        except Exception as e:
            print(f"[AUTO-RESTART] {name} crashed: {e}, restarting in 5s...")
        time.sleep(5)

threading.Thread(target=resilient_loop, args=(auto_connect_bootstrap, "auto_connect_bootstrap"), daemon=True).start()


# DEX Liquidity Pool
import json as _json

POOL_FILE = "liquidity_pool.json"

def load_pool():
    """คำนวณ pool state จาก chain (TEST คือโทเค็นทดลองในเครือข่าย ไม่ผูกกับเงินจริงใดๆ)"""
    pool = {"DYX": 100000, "TEST": 50000}
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
    price = liquidity_pool["TEST"] / liquidity_pool["DYX"]
    return jsonify({
        "DYX": liquidity_pool["DYX"],
        "TEST": liquidity_pool["TEST"],
        "price_dyx_test": round(price, 6),
        "note": "TEST is an in-network test token with no real-world monetary value. Not pegged to any currency."
    })

@app.route("/dex/swap", methods=["POST"])
def dex_swap():
    return jsonify({"error": "DEX temporarily disabled pending security review"}), 503
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
    return jsonify({"error": "DEX temporarily disabled pending security review"}), 503
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
    bal = node.balance(addr)
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
        if not is_valid_peer(peer):
            return jsonify({"error": "invalid peer"}), 400
        if not verify_peer(peer):
            return jsonify({"error": "peer verification failed"}), 400
        node.peers.add(peer)
        return jsonify({"success": True, "peer": peer})
    return jsonify({"error": "peer required"}), 400




def broadcast_tx(tx):
    """ส่ง transaction ไปให้ทุก peer พร้อม P2P authentication"""
    import requests as _req
    import json as _json

    tx_data = _json.dumps(tx, sort_keys=True, separators=(",", ":"))
    auth = sign_p2p_message(tx_data)

    payload = {
        **tx,
        "_p2p_ts": auth["timestamp"],
        "_p2p_sig": auth["signature"],
    }

    for peer in list(node.peers):
        try:
            _req.post(
                f"{peer}/receive_tx",
                json=payload,
                timeout=3
            )
        except:
            pass

@app.route("/receive_tx", methods=["POST"])
def receive_tx():
    """รับ transaction จาก peer"""
    tx = request.json
    if not tx:
        return jsonify({"error": "no tx"}), 400

    # ===== P2P authentication =====
    p2p_ts = tx.get("_p2p_ts")
    p2p_sig = tx.get("_p2p_sig")

    if p2p_ts is None or not p2p_sig:
        return jsonify({"error": "missing P2P authentication"}), 401

    import json as _json

    tx_data = _json.dumps(
        {k: v for k, v in tx.items()
         if k not in ("_p2p_ts", "_p2p_sig")},
        sort_keys=True,
        separators=(",", ":")
    )

    if not verify_p2p_message(p2p_ts, p2p_sig, tx_data):
        return jsonify({"error": "invalid P2P authentication"}), 401

    # Remove transport authentication fields before mempool admission.
    tx = {
        k: v for k, v in tx.items()
        if k not in ("_p2p_ts", "_p2p_sig")
    }

    # P2P must never accept reserved/system senders.
    sender = tx.get("from")
    reserved = {"SYSTEM", "GENESIS", "DEX", "NETWORK", "FAUCET"}
    if sender in reserved:
        return jsonify({"error": "reserved sender not allowed via P2P"}), 400

    # Economic validation before P2P mempool admission.
    # Reject malformed/non-finite monetary values.
    import math

    try:
        amount = float(tx.get("amount"))
        fee = float(tx.get("fee", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid amount or fee"}), 400

    if not math.isfinite(amount) or not math.isfinite(fee):
        return jsonify({"error": "invalid amount or fee"}), 400

    if amount <= 0:
        return jsonify({"error": "invalid amount"}), 400

    if fee < 0:
        return jsonify({"error": "invalid fee"}), 400

    min_fee = get_min_fee()
    if fee < min_fee:
        return jsonify({"error": f"Fee too low. Minimum: {min_fee} DYX"}), 400

    if node.balance(sender) < amount + fee:
        return jsonify({"error": "insufficient balance"}), 400

    # Reject duplicate/replayed transactions before mempool admission.
    if is_duplicate_tx(tx):
        return jsonify({"status": "already have tx"})

    if check_replay(tx):
        return jsonify({"error": "replay transaction"}), 400

    # Every normal P2P transaction must pass signature/address validation.
    if not verify_tx_signature(tx):
        return jsonify({"error": "invalid signature"}), 400

    node.mempool.append(tx)

    # Relay only validated transactions.
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

        # เก็บ chain เดิมไว้ก่อนเปลี่ยน node.chain
        old_chain = node.chain

        # หา transaction ที่ยืนยันแล้วใน chain ใหม่
        confirmed = set()
        for block in new_chain:
            for tx in block.get("transactions", []):
                sig = tx.get("signature", "")
                if sig:
                    confirmed.add(sig)

        # คืน transaction จาก chain เดิมที่ถูก orphan
        # ก่อนเปลี่ยน node.chain เพื่อไม่ให้ old chain หายไป
        for block in old_chain:
            for tx in block.get("transactions", []):
                sig = tx.get("signature", "")
                if sig and sig not in confirmed:
                    node.mempool.append(tx)

        # เปลี่ยน chain หลังจากเก็บ orphan transactions แล้ว
        node.chain = new_chain
        node.save_chain()

        return True

    return False



# Cache: address -> public_key (เพื่อไม่ต้องวนลูปทั้งเชนทุกครั้ง)
PUBKEY_CACHE = {}

def update_pubkey_cache_from_block(block):
    """เรียกทุกครั้งที่มี block ใหม่ เพื่ออัปเดต cache"""
    for t in block.get("transactions", []):
        sender = t.get("from")
        pk = t.get("public_key")
        if sender and pk and sender not in PUBKEY_CACHE:
            PUBKEY_CACHE[sender] = pk

def rebuild_pubkey_cache():
    """สร้าง cache ใหม่ทั้งหมดจาก chain ปัจจุบัน (เรียกตอน startup)"""
    PUBKEY_CACHE.clear()
    for block in node.chain:
        update_pubkey_cache_from_block(block)
    print(f"DEBUG: pubkey cache rebuilt, {len(PUBKEY_CACHE)} addresses")

# Cache: address -> public_key (เพื่อไม่ต้องวนลูปทั้งเชนทุกครั้ง)
PUBKEY_CACHE = {}

def update_pubkey_cache_from_block(block):
    """เรียกทุกครั้งที่มี block ใหม่ เพื่ออัปเดต cache"""
    for t in block.get("transactions", []):
        sender = t.get("from")
        pk = t.get("public_key")
        if sender and pk and sender not in PUBKEY_CACHE:
            PUBKEY_CACHE[sender] = pk

def rebuild_pubkey_cache():
    """สร้าง cache ใหม่ทั้งหมดจาก chain ปัจจุบัน (เรียกตอน startup)"""
    PUBKEY_CACHE.clear()
    for block in node.chain:
        update_pubkey_cache_from_block(block)
    print(f"DEBUG: pubkey cache rebuilt, {len(PUBKEY_CACHE)} addresses")

def verify_tx_signature(tx):
    """ตรวจสอบ transaction signature รองรับ current และ legacy protocol"""
    try:
        from ecdsa import VerifyingKey, SECP256k1
        import hashlib as _hl
        import json as _json

        sender = tx.get("from")

        if sender in ("SYSTEM", "GENESIS", "DEX", "NETWORK", "FAUCET"):
            return True

        signature_hex = tx.get("signature")
        if not signature_hex:
            return False

        signature = bytes.fromhex(signature_hex)

        msg_text = _json.dumps(
            {
                "amount": tx["amount"],
                "fee": tx.get("fee", 0),
                "from": tx["from"],
                "to": tx["to"]
            },
            sort_keys=True,
            separators=(",", ":")
        )

        msg = _hl.sha3_256(msg_text.encode()).digest()

        # CURRENT PROTOCOL
        pub_hex = PUBKEY_CACHE.get(sender)

        if not pub_hex:
            pub_hex = tx.get("public_key")

        if not pub_hex:
            for block in node.chain:
                for t in block.get("transactions", []):
                    if t.get("from") == sender and t.get("public_key"):
                        pub_hex = t["public_key"]
                        PUBKEY_CACHE[sender] = pub_hex
                        break
                if pub_hex:
                    break

        if pub_hex:
            pub_bytes = bytes.fromhex(pub_hex)

            derived_addr = pubkey_to_address(pub_bytes)
            if derived_addr.lower() != sender.lower():
                print(f"DEBUG: reject tx - public_key mismatch for {sender}")
                return False

            vk = VerifyingKey.from_string(
                pub_bytes,
                curve=SECP256k1
            )

            vk.verify_digest(signature, msg)
            return True

        # LEGACY PROTOCOL FALLBACK
        recovered_keys = VerifyingKey.from_public_key_recovery(
            signature,
            msg_text.encode(),
            SECP256k1,
            hashfunc=_hl.sha3_256
        )

        for vk in recovered_keys:
            recovered_pub = vk.to_string()
            recovered_addr = pubkey_to_address(recovered_pub)

            if recovered_addr.lower() != sender.lower():
                continue

            try:
                vk.verify_digest(signature, msg)
                return True
            except Exception:
                continue

        print(f"DEBUG: reject legacy tx from {sender} - recovery failed")
        return False

    except Exception as e:
        print(f"DEBUG: signature verify error: {e}")
        return False

def validate_block_balances(block, chain_before_block):
    """ตรวจสอบยอดเงินคงเหลือของทุก tx ในบล็อก (ป้องกัน double-spend)"""
    spent = {}
    for tx in block.get("transactions", []):
        sender = tx.get("from")
        if sender in ("SYSTEM", "GENESIS", "DEX", "NETWORK", "FAUCET"):
            continue
        try:
            amount = float(tx.get("amount", 0))
            fee = float(tx.get("fee", 0))
        except (TypeError, ValueError):
            print(f"DEBUG: reject block - invalid amount/fee for {sender}")
            return False

        if not __import__("math").isfinite(amount) or not __import__("math").isfinite(fee):
            print(f"DEBUG: reject block - non-finite amount/fee for {sender}")
            return False

        if amount <= 0:
            print(f"DEBUG: reject block - invalid amount for {sender}: {amount}")
            return False

        if fee < 0:
            print(f"DEBUG: reject block - invalid fee for {sender}: {fee}")
            return False

        total_needed = amount + fee

        balance = 0
        for b in chain_before_block:
            for t in b.get("transactions", []):
                if t.get("to") == sender:
                    balance += float(t.get("amount", 0))
                if t.get("from") == sender:
                    balance -= float(t.get("amount", 0)) + float(t.get("fee", 0))

        already_spent = spent.get(sender, 0)
        if balance - already_spent < total_needed:
            print(f"DEBUG: reject block - {sender} insufficient balance (has {balance - already_spent}, needs {total_needed})")
            return False

        spent[sender] = already_spent + total_needed

    return True

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


def verify_tx_signature_with_chain(tx, chain_context):
    """Pure transaction signature validation for candidate-chain validation.

    Does NOT read or mutate PUBKEY_CACHE.
    Uses tx.public_key when available; otherwise searches chain_context.
    Supports current and legacy signature protocols.
    """
    try:
        from ecdsa import VerifyingKey, SECP256k1
        import hashlib as _hl
        import json as _json

        sender = tx.get("from")

        if sender in ("SYSTEM", "GENESIS", "DEX", "NETWORK", "FAUCET"):
            return True

        signature_hex = tx.get("signature")
        if not signature_hex:
            return False

        signature = bytes.fromhex(signature_hex)

        msg_text = _json.dumps(
            {
                "amount": tx["amount"],
                "fee": tx.get("fee", 0),
                "from": tx["from"],
                "to": tx["to"]
            },
            sort_keys=True,
            separators=(",", ":")
        )

        msg = _hl.sha3_256(msg_text.encode()).digest()

        # Prefer public_key carried by the transaction.
        pub_hex = tx.get("public_key")

        # Legacy transactions may not carry public_key.
        if not pub_hex:
            for block in chain_context:
                for t in block.get("transactions", []):
                    if (
                        t.get("from") == sender
                        and t.get("public_key")
                    ):
                        pub_hex = t["public_key"]
                        break
                if pub_hex:
                    break

        # Current protocol: explicit public key.
        if pub_hex:
            pub_bytes = bytes.fromhex(pub_hex)

            derived_addr = pubkey_to_address(pub_bytes)
            if derived_addr.lower() != sender.lower():
                return False

            vk = VerifyingKey.from_string(
                pub_bytes,
                curve=SECP256k1
            )

            vk.verify_digest(signature, msg)
            return True

        # Legacy protocol: recover public key from signature.
        recovered_keys = VerifyingKey.from_public_key_recovery(
            signature,
            msg_text.encode(),
            SECP256k1,
            hashfunc=_hl.sha3_256
        )

        for vk in recovered_keys:
            recovered_pub = vk.to_string()
            recovered_addr = pubkey_to_address(recovered_pub)

            if recovered_addr.lower() != sender.lower():
                continue

            try:
                vk.verify_digest(signature, msg)
                return True
            except Exception:
                continue

        return False

    except Exception:
        return False


def validate_chain(chain):
    """ตรวจสอบ chain แบบ deterministic:
    Legacy history ใช้ difficulty ที่บันทึกไว้เมื่อมี
    และ replay rule เมื่อไม่มี
    Consensus V1 ใช้ fixed PoW ตั้งแต่ block 10208
    """
    import hashlib as _hl
    import json as _json

    for i in range(1, len(chain)):
        block = chain[i]
        prev = chain[i - 1]

        # 1. Block index
        if block.get("index") != i:
            print(f"Invalid index at block {i}")
            return False

        # 2. Previous block linkage
        if block.get("prev_hash") != prev.get("hash"):
            print(f"Invalid prev_hash at block {i}")
            return False

        # 3. Canonical SHA3-256 block hash
        raw = _hl.sha3_256(
            _json.dumps(
                {k: v for k, v in block.items() if k != "hash"},
                sort_keys=True
            ).encode()
        ).hexdigest()

        if raw != block.get("hash"):
            print(f"Invalid hash at block {i}")
            return False

        # 4. Deterministic transaction validation
        # Do not use verify_tx_signature() here because that function
        # depends on/mutates runtime PUBKEY_CACHE and node.chain.
        for tx in block.get("transactions", []):
            if not verify_tx_signature_with_chain(tx, chain[:i]):
                print(f"Invalid transaction signature at block {i}")
                return False

        # Deterministic balance / double-spend validation
        if not validate_block_balances(block, chain[:i]):
            print(f"Invalid transaction balance/state at block {i}")
            return False

        # 5. Consensus boundary
        if block.get("index", -1) >= CONSENSUS_V1_HEIGHT:
            # Consensus V1: fixed deterministic PoW
            if not validate_block_pow_ctx(block, chain[:i]):
                print(f"Invalid Consensus V1 PoW at block {i}")
                return False
            if block.get("index", -1) >= CONSENSUS_V2_HEIGHT and not validate_block_time_v2(block, chain[:i]):
                print(f"Invalid V2 timestamp at block {i}")
                return False

        else:
            # Legacy history:
            # Explicit difficulty field is authoritative.
            block_diff = block.get("difficulty")

            if block_diff:
                required_diff = block_diff
            else:
                required_diff = get_difficulty(chain[:i])

            if not block.get("hash", "").startswith(required_diff):
                print(
                    f"Invalid legacy PoW at block {i}: "
                    f"required={required_diff} "
                    f"actual_zeros={len(block.get('hash', '')) - len(block.get('hash', '').lstrip('0'))}"
                )
                return False

    return True

def _block_work(block, chain_prefix):
    """Actual proof-of-work for one block: inverse of its accept threshold."""
    idx = block.get("index", -1)
    if idx >= CONSENSUS_V2_HEIGHT:
        try:
            target = int(block.get("target", "0"), 16)
        except ValueError:
            return 0
        return (1 << 256) // max(target, 1)
    diff = block.get("difficulty") or ("0" * len((block.get("hash","")) ) )
    zeros = len(block.get("hash","")) - len(block.get("hash","").lstrip("0"))
    return 16 ** zeros

def _chain_work(chain):
    total = 0
    for i, b in enumerate(chain):
        total += _block_work(b, chain[:i])
    return total

def auto_sync_loop():
    import time
    time.sleep(15)  # รอให้ node start ก่อน
    while True:
        try:
            longest = node.chain
            for peer in list(node.peers):
                try:
                    is_onion = ".onion" in peer
                    r = peer_request("get", f"{peer}/chain", timeout=(90 if is_onion else 8))
                    peer_chain = r.json()
                    if not isinstance(peer_chain, list) or len(peer_chain) > 200000:
                        continue
                    if validate_chain(peer_chain):
                        peer_work = _chain_work(peer_chain)
                        cur_work = _chain_work(longest)
                        if peer_work > cur_work:
                            longest = peer_chain
                            print(f"Found higher work chain from {peer}: {len(peer_chain)} blocks")
                except Exception as _pe:
                    print(f"Sync attempt failed for {peer}: {_pe}")
            if reorg_chain(longest):
                print(f"Auto-synced/reorged to {len(node.chain)} blocks")
        except Exception as e:
            print(f"Auto-sync error: {e}")
        time.sleep(30)

# TEMPORARILY DISABLED: auto-sync/reorg safety lock
PEERS_FILE = "peers.json"
MAX_PEERS = 100
MAX_NEW_PEERS_PER_ROUND = 10
MAX_FAILURES = 5
peer_lock = threading.Lock()
peer_failures = {}

def save_peers():
    try:
        import json as _j

        port = int(os.environ.get("PORT", 6001))
        my_url = os.environ.get("MY_URL", "").strip()
        if not my_url:
            my_url = f"http://127.0.0.1:{port}"

        with peer_lock:
            clean_peers = sorted(
                p.rstrip("/")
                for p in node.peers
                if p and p.rstrip("/") != my_url.rstrip("/")
            )
            _j.dump(clean_peers, open(PEERS_FILE, "w"))

    except Exception as e:
        print(f"Peer save error: {e}")

def load_peers():
    try:
        import json as _j

        peers = _j.load(open(PEERS_FILE))

        port = int(os.environ.get("PORT", 6001))
        my_url = os.environ.get("MY_URL", "").strip()
        if not my_url:
            my_url = f"http://127.0.0.1:{port}"

        loaded = 0
        skipped_self = 0

        for p in peers:
            p = str(p).strip().rstrip("/")
            if not p:
                continue

            if p == my_url.rstrip("/"):
                skipped_self += 1
                continue

            if not is_valid_peer(p):
                continue

            if not verify_peer(p):
                continue

            node.peers.add(p)
            loaded += 1

        print(
            f"Loaded {loaded} peers "
            f"(skipped self: {skipped_self})"
        )

    except Exception as e:
        print(f"Peer load error: {e}")

def is_valid_peer(url):
    if not url: return False
    if not (url.startswith("http://") or url.startswith("https://")): return False
    if len(url) > 200: return False

    import re
    from urllib.parse import urlparse
    try:
        host = urlparse(url).hostname or ""
    except:
        return False

    blocked_patterns = [
        r'^localhost$', r'^127\.', r'^0\.', r'^10\.',
        r'^172\.(1[6-9]|2[0-9]|3[0-1])\.', r'^192\.168\.',
        r'^169\.254\.', r'^::1$', r'^fc00:', r'^fe80:'
    ]
    for pattern in blocked_patterns:
        if re.match(pattern, host):
            return False
    return True

import threading as _thr
_ONION_VERIFY_SLOTS = _thr.BoundedSemaphore(2)

def verify_peer(url):
    is_onion = ".onion" in url
    if is_onion and not _ONION_VERIFY_SLOTS.acquire(blocking=False):
        return False  # too many concurrent Tor verifications
    try:
        r = peer_request("get", f"{url}/api/v1/info", timeout=(45 if is_onion else 5))
        data = r.json()
        return (data.get("network_id") == 1337 and data.get("network") == "DYNAX")
    except: return False
    finally:
        if is_onion:
            _ONION_VERIFY_SLOTS.release()

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
    port = int(os.environ.get("PORT", 6001))
    my_url = os.environ.get("MY_URL", "").strip()
    if not my_url:
        my_url = f"http://127.0.0.1:{port}"

    while True:
        try:
            new_peers = set()
            with peer_lock:
                peers_copy = list(node.peers)
            for peer in peers_copy:
                try:
                    _is_onion = ".onion" in peer
                    r = peer_request("get", f"{peer}/peers", timeout=(45 if _is_onion else 5))
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

threading.Thread(target=resilient_loop, args=(peer_discovery_loop, "peer_discovery_loop"), daemon=True).start()
print("Peer discovery started")

threading.Thread(target=resilient_loop, args=(auto_sync_loop, "auto_sync_loop"), daemon=True).start()
print("Auto-sync/reorg: ENABLED (Tor-aware, V2-accurate work, mine/sync locked)")


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
    static_peers = []  # No hardcoded peers - fully decentralized bootstrap
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
                sender = tx.get("from")
                reserved = {"SYSTEM", "GENESIS", "DEX", "NETWORK", "FAUCET"}

                if sender in reserved:
                    continue

                # Economic validation before peer mempool admission.
                import math

                try:
                    amount = float(tx.get("amount"))
                    fee = float(tx.get("fee", 0))
                except (TypeError, ValueError):
                    continue

                if not math.isfinite(amount) or not math.isfinite(fee):
                    continue

                if amount <= 0:
                    continue

                if fee < 0:
                    continue

                min_fee = get_min_fee()
                if fee < min_fee:
                    continue

                if node.balance(sender) < amount + fee:
                    continue

                if is_duplicate_tx(tx) or check_replay(tx):
                    continue

                if not verify_tx_signature(tx):
                    continue

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

threading.Thread(target=resilient_loop, args=(mempool_sync_loop, "mempool_sync_loop"), daemon=True).start()
print("Mempool sync started")


def reconstruct_state():
    """คำนวณ state ทั้งหมดจาก chain ล้วนๆ"""
    state = {
        "balances": {},
        "dex_pool": {"DYX": 100000, "TEST": 50000},
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

P2P_SECRET = os.environ.get("P2P_SECRET")
if not P2P_SECRET:
    raise RuntimeError("P2P_SECRET is required")

def sign_p2p_message(data):
    """สร้าง signature สำหรับ P2P message"""
    timestamp = int(_time2.time())
    payload = f"{timestamp}:{data}"
    sig = _hmac.new(
        P2P_SECRET.encode(),
        payload.encode(),
        _hl2.sha3_256
    ).hexdigest()
    return {"timestamp": timestamp, "signature": sig}

def verify_p2p_message(timestamp, signature, data):
    """ตรวจสอบ P2P message"""
    # Reject malformed authentication input without raising exceptions.
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError, OverflowError):
        return False

    if not isinstance(signature, str) or not signature:
        return False

    # ตรวจ timestamp ไม่เกิน 60 วินาที
    if abs(int(_time2.time()) - timestamp_int) > 60:
        return False

    payload = f"{timestamp}:{data}"
    expected = _hmac.new(
        P2P_SECRET.encode(),
        payload.encode(),
        _hl2.sha3_256
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
    auth = sign_p2p_message(block_data)
    
    for peer in list(node.peers):
        try:
            _req.post(f"{peer}/receive_block", 
                json={**block, "_p2p_ts": auth["timestamp"], "_p2p_sig": auth["signature"]},
                timeout=5)
        except:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 6001)))



def download_snapshot(peer):
    try:
        r = peer_request("get", f"{peer}/snapshot", timeout=20)
        data = r.json()

        if data["height"] > len(node.chain):
            node.chain = data["blocks"]
            node.peers.update(data.get("peers", []))
            node.save_chain()
            print(f"Snapshot synced: {len(node.chain)} blocks")

    except Exception as e:
        print("Snapshot sync failed:", e)


