import copy
import importlib.util
import json
import shutil
from pathlib import Path
from ecdsa import SigningKey, SECP256k1

ROOT = Path.cwd()
SRC = ROOT / "dynax_node_v20.py"
CHAIN = ROOT / "dynax_chain.json"

TMP = ROOT / "dynax_test_tmp" / "sandbox"
TMP.mkdir(parents=True, exist_ok=True)

SANDBOX_SRC = TMP / "dynax_node_v20.py"
SANDBOX_CHAIN = TMP / "dynax_chain.json"

shutil.copy2(SRC, SANDBOX_SRC)
shutil.copy2(CHAIN, SANDBOX_CHAIN)

def snapshot(path):
    c = json.loads(Path(path).read_text())
    return (len(c), c[-1]["index"], c[-1]["hash"])

print("=== DYNAX DOUBLE-SPEND V3 : SANDBOX ONLY ===")

prod_before = snapshot(CHAIN)
print("PRODUCTION BEFORE:", prod_before)

# Load copied source only.
spec = importlib.util.spec_from_file_location("dynax_double_spend_v3", SANDBOX_SRC)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

# Redirect sandbox persistence.
if hasattr(d, "CHAIN_FILE"):
    d.CHAIN_FILE = str(SANDBOX_CHAIN)

# Create fresh sandbox node.
n = d.DynaxNode()

if hasattr(n, "CHAIN_FILE"):
    n.CHAIN_FILE = str(SANDBOX_CHAIN)

# Rebind module-global node because several helpers use it.
d.node = n

# Completely isolate P2P.
n.peers = []

if hasattr(d, "peer_request"):
    d.peer_request = lambda *args, **kwargs: None

print("SANDBOX START:",
      len(n.chain),
      n.chain[-1]["index"],
      n.chain[-1]["hash"])

# ------------------------------------------------------------
# Simulate the proposed mempool-recovery fix IN MEMORY ONLY.
# Production source is not modified.
# ------------------------------------------------------------
original_mine = d.DynaxNode.mine

def sandbox_safe_mine(self, miner):
    mempool_before = copy.deepcopy(self.mempool)
    chain_before = copy.deepcopy(self.chain)

    result = original_mine(self, miner)

    if (
        isinstance(result, dict)
        and isinstance(result.get("error"), str)
        and result["error"].startswith("local validation:")
        and self.chain == chain_before
    ):
        self.mempool = mempool_before

    return result

d.DynaxNode.mine = sandbox_safe_mine

# ------------------------------------------------------------
# Create ephemeral sender/recipients.
# ------------------------------------------------------------
sk = SigningKey.generate(curve=SECP256k1)
vk = sk.get_verifying_key()

sender = d.pubkey_to_address(vk.to_string())

a_sk = SigningKey.generate(curve=SECP256k1)
b_sk = SigningKey.generate(curve=SECP256k1)

recipient_a = d.pubkey_to_address(a_sk.get_verifying_key().to_string())
recipient_b = d.pubkey_to_address(b_sk.get_verifying_key().to_string())

print("EPHEMERAL SENDER:", sender)
print("RECIPIENT A:", recipient_a)
print("RECIPIENT B:", recipient_b)

# ------------------------------------------------------------
# Fund sender using sandbox mining.
# ------------------------------------------------------------
n.mempool = []

fund_result = n.mine(sender)

print("FUND RESULT:", fund_result)

sender_balance = n.balance(sender)

if sender_balance < 1.0:
    print("FUNDING: FAIL balance=", sender_balance)
    raise SystemExit(1)

print("FUNDING: PASS balance=", sender_balance)

# ------------------------------------------------------------
# Build two individually valid transactions spending the same
# 1.0 DYX balance.
# Each is valid alone, but both cannot fit in one block.
# ------------------------------------------------------------
def make_tx(to_addr):
    amount = 0.50
    fee = 0.01

    msg = json.dumps(
        {
            "amount": amount,
            "fee": fee,
            "from": sender,
            "to": to_addr,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = d.hashlib.sha3_256(msg.encode()).digest()
    signature = sk.sign_digest(digest)

    return {
        "from": sender,
        "to": to_addr,
        "amount": amount,
        "fee": fee,
        "signature": signature.hex(),
        "public_key": vk.to_string().hex(),
        "timestamp": 2,
    }

tx_a = make_tx(recipient_a)
tx_b = make_tx(recipient_b)

print("TX-A VERIFY:", d.verify_tx_signature(tx_a))
print("TX-B VERIFY:", d.verify_tx_signature(tx_b))

n.mempool = [tx_a, tx_b]

before_len = len(n.chain)
before_index = n.chain[-1]["index"]
before_hash = n.chain[-1]["hash"]

before_sender = n.balance(sender)
before_a = n.balance(recipient_a)
before_b = n.balance(recipient_b)
before_pool = copy.deepcopy(n.mempool)

print("BEFORE MINE:")
print("  chain:", before_len, before_index)
print("  last:", before_hash)
print("  sender:", before_sender)
print("  A:", before_a)
print("  B:", before_b)
print("  mempool:", len(before_pool))

# ------------------------------------------------------------
# Attempt to mine both conflicting transactions.
# Expected: block rejected, chain/state unchanged,
# mempool restored to 2.
# ------------------------------------------------------------
result = n.mine(sender)

print("MINE RESULT:", result)

after_len = len(n.chain)
after_index = n.chain[-1]["index"]
after_hash = n.chain[-1]["hash"]

after_sender = n.balance(sender)
after_a = n.balance(recipient_a)
after_b = n.balance(recipient_b)
after_pool = copy.deepcopy(n.mempool)

print("AFTER MINE:")
print("  chain:", after_len, after_index)
print("  last:", after_hash)
print("  sender:", after_sender)
print("  A:", after_a)
print("  B:", after_b)
print("  mempool:", len(after_pool))

checks = []

checks.append((
    "TX-A VALID",
    d.verify_tx_signature(tx_a) is True
))

checks.append((
    "TX-B VALID",
    d.verify_tx_signature(tx_b) is True
))

checks.append((
    "BLOCK REJECTED",
    isinstance(result, dict)
    and result.get("error")
    == "local validation: insufficient balance in block"
))

checks.append((
    "CHAIN UNCHANGED",
    after_len == before_len
    and after_index == before_index
    and after_hash == before_hash
))

checks.append((
    "STATE UNCHANGED",
    after_sender == before_sender
    and after_a == before_a
    and after_b == before_b
))

checks.append((
    "MEMPOOL RESTORED",
    len(after_pool) == len(before_pool)
    and {
        tx["signature"] for tx in after_pool
    } == {
        tx["signature"] for tx in before_pool
    }
))

checks.append((
    "CHAIN VALID",
    bool(d.validate_chain(n.chain))
))

for name, ok in checks:
    print(f"{name}: {'PASS' if ok else 'FAIL'}")

# ------------------------------------------------------------
# Sandbox persistence.
# ------------------------------------------------------------
saved = json.loads(SANDBOX_CHAIN.read_text())

sandbox_persist = (
    len(saved),
    saved[-1]["index"],
    saved[-1]["hash"],
)

print("SANDBOX PERSISTENCE:", sandbox_persist)

# ------------------------------------------------------------
# Production protection.
# Must show BOTH BEFORE and AFTER.
# ------------------------------------------------------------
prod_after = snapshot(CHAIN)

print("PRODUCTION AFTER:", prod_after)

production_protected = prod_before == prod_after

print(
    "PRODUCTION PROTECTED:",
    "PASS" if production_protected else "FAIL"
)

all_ok = all(ok for _, ok in checks) and production_protected

print("=== FINAL:", "ALL PASS" if all_ok else "FAIL", "===")

if not all_ok:
    raise SystemExit(1)
