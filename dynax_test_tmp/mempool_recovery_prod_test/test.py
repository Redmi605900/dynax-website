from pathlib import Path
import os
import sys
import json
import copy
import hashlib

ROOT = Path.cwd()

print("=== DYNAX PRODUCTION PATCH SANDBOX TEST ===")

# Import the patched production source from this isolated directory.
sys.path.insert(0, str(ROOT))

import dynax_node_v20 as d

# Create a fresh node using ONLY the copied sandbox chain.
node = d.DynaxNode()
node.peers = []

before_chain = copy.deepcopy(node.chain)
before_len = len(node.chain)
before_last = node.chain[-1]["hash"]

print("SANDBOX INITIAL BLOCKS:", before_len)
print("SANDBOX INITIAL LAST:", node.chain[-1]["index"])
print("SANDBOX INITIAL HASH:", before_last)

# Generate ephemeral sender/recipient keys.
from ecdsa import SigningKey, SECP256k1

sender_sk = SigningKey.generate(curve=SECP256k1)
sender_vk = sender_sk.get_verifying_key()

recipient_sk = SigningKey.generate(curve=SECP256k1)
recipient_vk = recipient_sk.get_verifying_key()

sender_pub = sender_vk.to_string()
recipient_pub = recipient_vk.to_string()

sender = d.pubkey_to_address(sender_pub)
recipient = d.pubkey_to_address(recipient_pub)

# Give sender exactly 1 DYX in the SANDBOX only.
funding_tx = {
    "from": "SYSTEM",
    "to": sender,
    "amount": 1.0,
    "fee": 0,
    "timestamp": 1,
}

funding_block = {
    "index": len(node.chain),
    "timestamp": 1,
    "transactions": [funding_tx],
    "prev_hash": node.chain[-1]["hash"],
    "nonce": 0,
}

funding_raw = json.dumps(funding_block, sort_keys=True)
funding_block["hash"] = hashlib.sha3_256(
    funding_raw.encode()
).hexdigest()

node.chain.append(funding_block)

def make_tx():
    amount = 0.51
    fee = max(float(d.get_min_fee()), 0.01)

    msg_dict = {
        "amount": amount,
        "fee": fee,
        "from": sender,
        "to": recipient,
    }

    msg_text = json.dumps(
        msg_dict,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = hashlib.sha3_256(msg_text.encode()).digest()
    sig = sender_sk.sign_digest(digest).hex()

    return {
        **msg_dict,
        "signature": sig,
        "public_key": sender_pub.hex(),
        "timestamp": 1,
    }

tx_a = make_tx()
tx_b = make_tx()

print("TX-A VALID:", d.verify_tx_signature(tx_a))
print("TX-B VALID:", d.verify_tx_signature(tx_b))

node.mempool = [tx_a, tx_b]

mempool_before = copy.deepcopy(node.mempool)
chain_before_mine = copy.deepcopy(node.chain)

print("MEMPOOL BEFORE:", len(node.mempool))

# IMPORTANT:
# This calls the ACTUAL patched DynaxNode.mine().
result = node.mine(sender)

print("MINE RESULT:", result)
print("MEMPOOL AFTER:", len(node.mempool))
print("CHAIN AFTER:", len(node.chain))

print("=== ASSERTIONS ===")

rejected = (
    isinstance(result, dict)
    and isinstance(result.get("error"), str)
    and result["error"].startswith("local validation:")
)

chain_unchanged = node.chain == chain_before_mine
mempool_restored = node.mempool == mempool_before
production_snapshot_protected = (
    before_len == 10211
    and before_chain[-1]["index"] == 10210
    and before_last == "0000fc543fb332358be6bf5843d411a928c71779e09093a1a7c0b613171e88e0"
)

checks = {
    "TX_A_VALID": d.verify_tx_signature(tx_a),
    "TX_B_VALID": d.verify_tx_signature(tx_b),
    "BLOCK_REJECTED": rejected,
    "CHAIN_UNCHANGED": chain_unchanged,
    "MEMPOOL_RESTORED": mempool_restored,
    "PRODUCTION_SNAPSHOT_PROTECTED": production_snapshot_protected,
}

for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")

print("=== FINAL ===")
print("ALL PASS:", all(checks.values()))
