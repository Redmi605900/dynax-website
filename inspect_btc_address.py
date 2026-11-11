import json
import time
import urllib.request
import urllib.error

ADDRESS = "178xdcnyoRCsL579ydRzJcFjLmiwxqRkJX"
BASE = "https://blockstream.info/api"

def get_json(path, retries=4):
    url = BASE + path
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "BTC-Address-Audit/1.0"}
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            print("Request failed:", type(exc).__name__, str(exc)[:160])
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
    return None

print("ADDRESS:", ADDRESS)
print("SOURCE: Blockstream public API")
print("MODE: READ ONLY")
print()

info = get_json("/address/" + ADDRESS)
if info is None:
    print("RESULT: API unavailable; no conclusion.")
    raise SystemExit(1)

chain = info.get("chain_stats", {})
mempool = info.get("mempool_stats", {})

funded = chain.get("funded_txo_sum", 0)
spent = chain.get("spent_txo_sum", 0)
balance = funded - spent

print("CONFIRMED_TX_COUNT:", chain.get("tx_count"))
print("CONFIRMED_FUNDED_SATS:", funded)
print("CONFIRMED_SPENT_SATS:", spent)
print("CONFIRMED_BALANCE_BTC:", balance / 100_000_000)
print("MEMPOOL_TX_COUNT:", mempool.get("tx_count"))
print()

txs = []
last_seen = None
max_txs = 100

while len(txs) < max_txs:
    path = "/address/" + ADDRESS + "/txs"
    if last_seen:
        path += "/chain/" + last_seen

    batch = get_json(path)
    if not isinstance(batch, list) or not batch:
        break

    txs.extend(batch)
    last_seen = batch[-1].get("txid")

    if len(batch) < 25:
        break

    time.sleep(0.3)

txs = txs[:max_txs]
print("TRANSACTIONS_FETCHED:", len(txs))

seen_pubkeys = set()
matching_outputs = 0
spent_matching_outputs = 0
pubkeys_from_matching_spends = set()

for tx in txs:
    txid = tx.get("txid", "?")

    for vout in tx.get("vout", []):
        script = vout.get("scriptpubkey_address")
        if script == ADDRESS:
            matching_outputs += 1
            if vout.get("scriptpubkey_type") == "p2tr":
                print("TAPROOT_OUTPUT_FOUND:", txid)

    for vin in tx.get("vin", []):
        prev = vin.get("prevout") or {}
        if prev.get("scriptpubkey_address") != ADDRESS:
            continue

        spent_matching_outputs += 1
        candidates = []

        # Public keys may appear in scriptSig or witness.
        scriptsig = vin.get("scriptsig", "")
        if scriptsig:
            candidates.append(scriptsig)

        candidates.extend(vin.get("witness") or [])

        for item in candidates:
            if not isinstance(item, str):
                continue
            raw = item.lower()
            # Compressed/uncompressed public-key encodings.
            if (
                (len(raw) == 66 and raw[:2] in ("02", "03"))
                or (len(raw) == 130 and raw.startswith("04"))
            ):
                pubkeys_from_matching_spends.add(raw)

print("ADDRESS_OUTPUTS_FOUND:", matching_outputs)
print("SPENDS_OF_ADDRESS_OUTPUTS_FOUND:", spent_matching_outputs)
print("PUBLIC_KEYS_VISIBLE_IN_MATCHING_SPENDS:",
      len(pubkeys_from_matching_spends))

for key in sorted(pubkeys_from_matching_spends):
    print("PUBLIC_KEY_HEX:", key)

if not txs:
    print("NOTE: No transaction details fetched.")
else:
    print("NOTE: Limited to the latest fetched transactions.")
    print("This scan does not prove a private-key weakness.")

print("DONE")
