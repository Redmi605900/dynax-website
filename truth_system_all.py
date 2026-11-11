import requests, json, time, re
from collections import Counter

class TruthSystem:
    def __init__(self):
        self.rpc_url = "https://arbitrum-one.publicnode.com"
        self.explorer_api = "https://api.arbiscan.io/api"
        self.dataset_path = "truth_dataset.json"
        self.rules = self._load_constitution()

    # === 1. GROUND TRUTH VERIFICATION ===
    def verify_balance(self, address: str) -> dict:
        try:
            resp = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0", "method": "eth_getBalance",
                "params": [address, "latest"], "id": 1
            }, timeout=10).json()
            wei = int(resp.get('result', '0x0'), 16)
            return {"source": "RPC", "balance_eth": wei / 1e18, "is_verified": True}
        except Exception as e:
            return {"source": "RPC_FAILED", "error": str(e), "is_verified": False}

    def verify_tx(self, tx_hash: str) -> dict:
        try:
            resp = requests.get(self.explorer_api, params={
                "module": "proxy", "action": "eth_getTransactionReceipt",
                "txhash": tx_hash, "apikey": "YourApiKeyToken"
            }, timeout=10).json()
            status = resp.get('result', {}).get('status')
            return {
                "tx_hash": tx_hash,
                "status": "SUCCESS" if status == "0x1" else "FAILED" if status == "0x0" else "PENDING",
                "is_verified": status is not None
            }
        except Exception as e:
            return {"tx_hash": tx_hash, "status": "UNKNOWN", "is_verified": False}

    # === 2. CONSTITUTIONAL ENFORCEMENT ===
    def _load_constitution(self) -> dict:
        try:
            with open(self.dataset_path, "r") as f: data = json.load(f)
        except FileNotFoundError:
            return {"high_risk_patterns": [], "enforcement_count": 0}
        
        counter = Counter()
        for entry in data:
            claim = entry.get("original_claim", "")
            if any(kw in claim for kw in ["สำเร็จ", "Success", "✅"]):
                counter[claim[:50]] += 1
        
        return {
            "high_risk_patterns": [p for p, _ in counter.most_common(5)],
            "enforcement_count": len(data)
        }

    def get_priority(self, response: str) -> float:
        priority = 0.5
        for pattern in self.rules["high_risk_patterns"]:
            if pattern in response: priority += 0.3
        priority += min(self.rules["enforcement_count"] * 0.01, 0.2)
        return min(priority, 1.0)

    def enforce_rule(self, claim: str, verified: bool) -> str:
        keywords = ["สำเร็จ", "Success", "✅", "DONE"]
        has_claim = any(kw in claim for kw in keywords)
        if has_claim and not verified:
            return f"⛔ TRUTH VIOLATION: {claim}\nCORRECTED: ไม่มีการยืนยันจากแหล่งข้อมูลจริง"
        return claim

    # === 3. AUTO GUARD & LOGGING ===
    def process_response(self, user_input: str, ai_response: str) -> str:
        blockchain_kw = ["tx", "hash", "balance", "send", "arbitrum", "eth"]
        is_related = any(kw in (user_input + ai_response).lower() for kw in blockchain_kw)
        if not is_related: return ai_response

        verified = False
        hashes = re.findall(r'0x[a-fA-F0-9]{64}', ai_response)
        addrs = re.findall(r'0x[a-fA-F0-9]{40}', ai_response)

        for h in hashes:
            r = self.verify_tx(h)
            if r.get('is_verified'): verified = True
        if addrs and not hashes:
            for a in addrs:
                r = self.verify_balance(a)
                if r.get('is_verified') and r.get('balance_eth', 0) > 0: verified = True

        final = self.enforce_rule(ai_response, verified)
        if final != ai_response:
            self.log_correction(ai_response, final, {"verified": verified})
        return final

    def log_correction(self, original: str, corrected: str, result: dict):
        entry = {
            "timestamp": time.time(), "original_claim": original,
            "corrected_response": corrected, "verification_result": result
        }
        try:
            with open(self.dataset_path, "r+") as f:
                data = json.load(f); data.append(entry); f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)
        except FileNotFoundError:
            with open(self.dataset_path, "w") as f:
                json.dump([entry], f, ensure_ascii=False, indent=2)
        print(f"📝 Logged correction to {self.dataset_path}")

# === TEST RUN ===
if __name__ == "__main__":
    ts = TruthSystem()
    print("🧠 TRUTH SYSTEM ALL-IN-ONE INITIALIZED")
    print(f"Constitution Priority: {ts.get_priority('✅ TX สำเร็จ'):.2f}")
    
    fake = "✅ ส่ง TX สำเร็จ Hash: 0x1234... เงินเข้า 0xfb8a...bc61 แล้ว"
    result = ts.process_response("ส่งเงินให้ฉัน", fake)
    print(f"\nOriginal: {fake}")
    print(f"Corrected: {result}")
    print("\n✅ System Ready. Use ts.process_response(user_query, ai_reply) in your workflow.")
