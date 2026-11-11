import json
import urllib.request
import time

ADDRESS = "178xdcnyoRCsL579ydRzJcFjLmiwxqRkJX"
BASE = "https://blockstream.info/api"

def get(path):
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": "BTC-Script-Audit/1.0"}
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())

print("ADDRESS:", ADDRESS)
info = get("/address/" + ADDRESS)
stats = info["chain_stats"]
print("CONFIRMED_TX_COUNT:", stats["tx_count"])
print("CONFIRMED_BALANCE_BTC:",
      (stats["funded_txo_sum"] - stats["spent_txo_sum"]) / 100_000_000)

txs = []
last = None

while len(txs) < 100:
    path = "/address/" + ADDRESS + "/txs"
    if last:
        path += "/chain/" + last

    batch = get(path)
    if not batch:
        break

    txs.extend(batch)
    last = batch[-1]["txid"]

    if len(batch) < 25:
        break
    time.sleep(0.25)

found = 0
for tx in txs:
    for index, vout in enumerate(tx.get("vout", [])):
        if vout.get("scriptpubkey_address") != ADDRESS:
            continue

        found += 1
        print("\nTXID:", tx["txid"])
        print("VOUT_INDEX:", index)
        print("VALUE_BTC:", vout["value"] / 100_000_000)
        print("SCRIPT_TYPE:", vout.get("scriptpubkey_type"))
        print("SCRIPT_PUBKEY:", vout.get("scriptpubkey"))

print("\nTRANSACTIONS_FETCHED:", len(txs))
print("MATCHING_OUTPUTS:", found)
print("DONE")
