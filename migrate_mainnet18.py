import json

SRC = "/data/data/com.termux/files/home/dynax_chain_MAINNET_18BLOCK.json"
DST = "/data/data/com.termux/files/home/qchain-website/dynax_chain_6001_migrated.json"

src_chain = json.load(open(SRC))

new_chain = []

for b in src_chain:
    nb = {
        "index": b["index"],
        "prev_hash": b["prev_hash"],
        "data": b["transactions"],
        "timestamp": b["timestamp"],
        "nonce": b["nonce"],
        "hash": b["hash"]
    }
    new_chain.append(nb)

with open(DST, "w") as f:
    json.dump(new_chain, f, indent=2)

print("Migrated:", len(new_chain), "blocks")
print("Output:", DST)
