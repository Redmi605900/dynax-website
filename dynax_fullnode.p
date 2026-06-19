
import time
import json
import hashlib
import os
import requests
from flask import Flask, jsonify, request
from eth_account import Account
from eth_account.messages import encode_defunct

app = Flask(__name__)

# ─────────────────────────────
# CONFIGURATION - ใช้ไฟล์ Chain เดิมของคุณ
# ─────────────────────────────
CHAIN_FILE = "dynax_chain.json"
chain = []
mempool = []
known_nodes = set()

DIFFICULTY_TARGET = "0" * 5  
MAX_TX_PER_BLOCK = 50  
BASE_REWARD = 50       

def load_chain():
    global chain
    print(f"📂 Loading chain from: {CHAIN_FILE}")
    
    if os.path.exists(CHAIN_FILE):
        try:
            with open(CHAIN_FILE, 'r') as f:
                loaded_chain = json.load(f)
            
            if isinstance(loaded_chain, list) and len(loaded_chain) > 0:
                chain.extend(loaded_chain)
                print(f"✅ Loaded {len(chain)} blocks from existing chain")
                
                if chain[0].get("index") == 0:
                    print("✅ Genesis block verified")
                else:
                    print("⚠️ Warning: First block is not Genesis")
            else:
                print("⚠️ Invalid chain format, creating new genesis")
                create_genesis_block()
        except json.JSONDecodeError as e:
            print(f"❌ JSON Error: {e}")
            print("⚠️ Creating backup and new chain")
            os.replace(CHAIN_FILE, CHAIN_FILE + ".corrupted")
            create_genesis_block()
        except Exception as e:
            print(f"❌ Error loading chain: {e}")            create_genesis_block()
    else:
            print("📄 No existing chain found, creating genesis block")

                    create_genesis_block()

def create_genesis_block():
    global chain
    genesis = {
        "index": 0,
        "timestamp": int(time.time()),
        "txs": [],
        "prev_hash": "0" * 64,
        "merkle_root": "0",
        "nonce": 0
    }
    
    raw = json.dumps(genesis, sort_keys=True)
    genesis["hash"] = hashlib.sha3_256(raw.encode()).hexdigest()
    
    chain = [genesis]
    save_chain()
    print("✅ Genesis block created")

def save_chain():
    tmp = CHAIN_FILE + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(chain, f, indent=2)
    os.replace(tmp, CHAIN_FILE)

def sha3_256(data):
    return hashlib.sha3_256(data.encode()).hexdigest()

def merkle_root(txs):
    if not txs:
        return "0"
    hashes = [sha3_256(json.dumps(tx, sort_keys=True)) for tx in txs]
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        new_level = []
        for i in range(0, len(hashes), 2):
            new_level.append(sha3_256(hashes[i] + hashes[i+1]))
        hashes = new_level
    return hashes[0]

def validate_chain(chain_to_validate):
    for i in range(1, len(chain_to_validate)):
        curr = chain_to_validate[i]
        prev = chain_to_validate[i - 1]
        if curr["index"] != prev["index"] + 1: return False        if curr["prev_hash"] != prev["hash"]: return False
        
        raw = json.dumps({
            "index": curr["index"], "timestamp": curr["timestamp"],
            "txs": curr["txs"], "prev_hash": curr["prev_hash"],
            "merkle_root": curr["merkle_root"], "nonce": curr["nonce"]
        }, sort_keys=True)
        
        if sha3_256(raw) != curr["hash"]: return False
        if not curr["hash"].startswith(DIFFICULTY_TARGET): return False
    return True

def create_block(txs):
    prev_hash = chain[-1]["hash"] if chain else "0"*64
    total_fees = sum(tx.get("fee", 0) for tx in txs)
    
    reward_tx = {
        "from": "SYSTEM", "to": "MINER_REWARD", 
        "amount": BASE_REWARD + total_fees, "fee": 0, "is_reward": True
    }
    final_txs = [reward_tx] + txs

    block = {
        "index": len(chain),
        "timestamp": int(time.time()),
        "txs": final_txs,
        "prev_hash": prev_hash,
        "merkle_root": merkle_root(final_txs),
        "nonce": 0
    }
    
    print(f"⛏️  Mining Block {block['index']} with Difficulty {len(DIFFICULTY_TARGET)}...")
    while True:
        raw = json.dumps(block, sort_keys=True)
        h = sha3_256(raw)
        if h.startswith(DIFFICULTY_TARGET):
            block["hash"] = h
            print(f"✅ Block {block['index']} Mined! Hash: {h[:16]}...")
            break
        block["nonce"] += 1
    return block

def mine():
    global chain, mempool
    if not mempool:
        return None
    
    sorted_mempool = sorted(mempool, key=lambda x: x.get("fee", 0), reverse=True)
    txs_to_mine = sorted_mempool[:MAX_TX_PER_BLOCK]
        for tx in txs_to_mine:
        mempool.remove(tx)
    
    block = create_block(txs_to_mine)
    
    if len(chain) == 0 or block["prev_hash"] == chain[-1]["hash"]:
        chain.append(block)
        save_chain()
        return block
    return None

def calculate_balance(address):
    balance = 0
    for block in chain:
        for tx in block.get("txs", []):
            if tx.get("to") == address:
                balance += tx.get("amount", 0)
            if tx.get("from") == address:
                balance -= tx.get("amount", 0)
    return balance

load_chain()

@app.route("/nodes/register", methods=["POST"])
def register_nodes():
    values = request.get_json()
    for node in values.get('nodes', []):
        known_nodes.add(node)
    return jsonify({"message": "Nodes registered", "total_peers": len(known_nodes)})

@app.route("/nodes/resolve", methods=["GET"])
def resolve():
    global chain
    max_length = len(chain)
    new_chain = None
    for node in known_nodes:
        try:
            res = requests.get(f"{node}/chain", timeout=3)
            if res.status_code == 200:
                remote_chain = res.json()
                if len(remote_chain) > max_length and validate_chain(remote_chain):
                    max_length = len(remote_chain)
                    new_chain = remote_chain
        except:
            continue
    if new_chain:
        chain = new_chain
        save_chain()
        return jsonify({"message": "Chain replaced (Longest Chain Rule)", "length": len(chain)})
    return jsonify({"message": "Chain is authoritative", "length": len(chain)})
@app.route("/tx", methods=["POST"])
def tx():
    data = request.get_json()
    required = ['from', 'to', 'amount', 'fee', 'signature']
    if not all(k in data for k in required):
        return jsonify({"error": "Missing fields"}), 400

    msg_dict = {"amount": data['amount'], "fee": data['fee'], "from": data['from'], "to": data['to']}
    message_text = json.dumps(msg_dict, sort_keys=True, separators=(',', ':'))

    try:
        message = encode_defunct(text=message_text)
        recovered_address = Account.recover_message(message, signature=data['signature'])
        if recovered_address.lower() != data['from'].lower():
            return jsonify({"error": "Invalid signature"}), 401

        mempool.append(data)
        mempool.sort(key=lambda x: x.get("fee", 0), reverse=True)
        
        tx_hash = sha3_256(message_text)
        return jsonify({"status": "accepted", "tx_hash": tx_hash, "mempool_position": 1})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/mine", methods=["GET"])
def mine_block():
    result = mine()
    return jsonify(result if result else {"status": "no tx in mempool"})

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify(chain)

@app.route("/balance/<address>", methods=["GET"])
def get_balance(address):
    balance = calculate_balance(address)
    return jsonify({"address": address, "balance": balance})

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "network": "DYNAX P2P (No Middleman)",
        "algorithm": "SHA3-256 (Keccak)",
        "blocks": len(chain),
        "mempool_size": len(mempool),
        "peers": len(known_nodes),
        "difficulty": len(DIFFICULTY_TARGET),
        "chain_file": CHAIN_FILE
    })
if __name__ == "__main__":
    print(f"=== DYNAX FULL NODE STARTED (SHA3-256 | Difficulty: {len(DIFFICULTY_TARGET)}) ===")
    print(f"📂 Using chain file: {CHAIN_FILE}")
    app.run(host="0.0.0.0", port=6001)
