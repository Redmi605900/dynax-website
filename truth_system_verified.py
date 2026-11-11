import requests, json, time, re, os, tempfile
from collections import Counter

class TruthSystemVerified:
    def __init__(self, dataset_path="truth_dataset.json"):
        self.rpc_url = "https://arbitrum-one.publicnode.com"
        self.explorer_api = "https://api.arbiscan.io/api"
        self.dataset_path = dataset_path
        self.rules = self._load_constitution()
        # Blacklist addresses that are known to be problematic or null
        self.blacklisted_addresses = [
            "0x0000000000000000000000000000000000000000",
            "0x000000000000000000000000000000000000dead"
        ]

    def verify_balance(self, address: str) -> dict:
        if address.lower() in [a.lower() for a in self.blacklisted_addresses]:
            return {"source": "BLACKLISTED", "is_verified": False, "wei": 0}

        try:
            resp = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0", "method": "eth_getBalance",
                "params": [address, "latest"], "id": 1
            }, timeout=10).json()
            
            result_hex = resp.get('result', '0x0')
            if not result_hex or result_hex == '0x':
                return {"source": "RPC_INVALID", "is_verified": False, "wei": 0}
                
            wei = int(result_hex, 16)
            return {
                "source": "RPC", 
                "balance_eth": wei / 1e18, 
                "is_verified": wei > 0, 
                "wei": wei
            }
        except Exception as e:
            return {"source": "RPC_FAILED", "error": str(e), "is_verified": False, "wei": 0}

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
        keywords = ["สำเร็จ", "Success", "✅", "DONE", "แล้ว"] # เพิ่ม "แล้ว" เพื่อจับประโยคบอกเล่า
        has_claim = any(kw in claim for kw in keywords)
        
        # ถ้ามีการเคลมความสำเร็จ (แม้แต่โดยนัย) และไม่ได้รับการยืนยัน
        if has_claim and not verified:
            return f"⛔ TRUTH VIOLATION: {claim}\nCORRECTED: ไม่มีการยืนยันจากแหล่งข้อมูลจริง"
        return claim

    def log_correction(self, original: str, corrected: str, result: dict):
        entry = {
            "timestamp": round(time.time(), 2), 
            "original_claim": original,
            "corrected_response": corrected, 
            "verification_result": result
        }
        
        try:
            if os.path.exists(self.dataset_path):
                with open(self.dataset_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                
                for prev in existing_data[-10:]:
                    if (prev.get("original_claim") == original and 
                        abs(prev.get("timestamp", 0) - entry["timestamp"]) < 5):
                        print(f" Skipped duplicate log (within 5s): {original[:30]}...")
                        return
                        
                existing_data.append(entry)
                write_data = existing_data
            else:
                write_data = [entry]
                
            fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.dataset_path) or '.', suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as tmp_f:
                    json.dump(write_data, tmp_f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self.dataset_path)
                print(f" Logged correction to {self.dataset_path}")
            except Exception:
                if os.path.exists(tmp_path): os.unlink(tmp_path)
                raise
                
        except Exception as e:
            print(f" Log failed: {e}")

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
            
        # FIX: ตรวจสอบ Address อย่างเข้มงวด
        if addrs and not hashes:
            for a in addrs:
                r = self.verify_balance(a)
                # ต้อง Verified=True AND มีเงินจริง AND ไม่อยู่ใน Blacklist
                if r.get('is_verified') and r.get('wei', 0) > 0: 
                    verified = True

        final = self.enforce_rule(ai_response, verified)
        if final != ai_response:
            self.log_correction(ai_response, final, {"verified": verified})
        return final

def run_tests():
    ts = TruthSystemVerified(dataset_path="test_truth_dataset.json")
    
    if os.path.exists("test_truth_dataset.json"): os.remove("test_truth_dataset.json")
    
    results = []
    
    # TEST 1: FAIL CASE
    raw_fail = " TX ส่งสำเร็จแล้ว! Hash: 0x1234abcd..."
    res_fail = ts.process_response("ส่งเงิน", raw_fail)
    passed_fail = ("TRUTH VIOLATION" in res_fail) and ("ไม่มีการยืนยัน" in res_fail)
    results.append(("FAIL_CASE", passed_fail, raw_fail, res_fail))
    
    # TEST 2: PASS CASE
    raw_pass = "สวัสดีครับ วันนี้สภาพอากาศดี"
    res_pass = ts.process_response("ทักทาย", raw_pass)
    passed_pass = (res_pass == raw_pass)
    results.append(("PASS_CASE", passed_pass, raw_pass, res_pass))
    
    # TEST 3: UNVERIFIABLE CASE (Address 0x000...000 ต้องถูกบล็อก)
    raw_unv = "เงินเข้ากระเป๋า 0x0000000000000000000000000000000000000000 แล้ว"
    res_unv = ts.process_response("เช็คเงิน", raw_unv)
    passed_unv = ("TRUTH VIOLATION" in res_unv or "ไม่มีการยืนยัน" in res_unv)
    results.append(("UNVERIFIABLE_CASE", passed_unv, raw_unv, res_unv))
    
    # TEST 4: DEDUPLICATION TEST
    ts.log_correction("Test Dup", "Corrected Dup", {"test": True})
    ts.log_correction("Test Dup", "Corrected Dup", {"test": True})
    dup_count = 0
    if os.path.exists("test_truth_dataset.json"):
        with open("test_truth_dataset.json") as f:
            data = json.load(f)
            dup_count = sum(1 for d in data if d.get("original_claim") == "Test Dup")
    passed_dedup = (dup_count == 1)
    results.append(("DEDUPLICATION_TEST", passed_dedup, f"Dups found: {dup_count}", "Expected: 1"))

    print("\n" + "="*60)
    print(" AUTOMATED TEST REPORT (HARDENED VERSION)")
    print("="*60)
    all_passed = True
    for name, passed, inp, out in results:
        status = " PASS" if passed else " FAIL"
        if not passed: all_passed = False
        print(f"{status} | {name}")
        if not passed:
            print(f"   Input:  {inp[:60]}")
            print(f"   Output: {out[:60]}")
    
    print("="*60)
    if all_passed:
        print(" ALL TESTS PASSED - System is verifiably correct")
    else:
        print(" SOME TESTS FAILED - Do NOT claim success")
    print("="*60)
    
    if os.path.exists("test_truth_dataset.json"): os.remove("test_truth_dataset.json")

if __name__ == "__main__":
    run_tests()
