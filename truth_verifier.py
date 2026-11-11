import requests
import json
import time

class GroundTruthVerifier:
    def __init__(self):
        self.rpc_url = "https://arbitrum-one.publicnode.com"
        self.explorer_api = "https://api.arbiscan.io/api"
        self.verified_cache = {}

    def verify_balance(self, address: str) -> dict:
        try:
            rpc_resp = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0", "method": "eth_getBalance", 
                "params": [address, "latest"], "id": 1
            }, timeout=10).json()
            rpc_wei = int(rpc_resp.get('result', '0x0'), 16)
            return {
                "source": "RPC_DIRECT", "balance_eth": rpc_wei / 1e18,
                "is_verified": True, "timestamp": time.time()
            }
        except Exception as e:
            return {"source": "RPC_FAILED", "error": str(e), "is_verified": False}

    def verify_tx_status(self, tx_hash: str) -> dict:
        try:
            resp = requests.get(self.explorer_api, params={
                "module": "proxy", "action": "eth_getTransactionReceipt",
                "txhash": tx_hash, "apikey": "YourApiKeyToken"
            }, timeout=10).json()
            status = resp.get('result', {}).get('status', None)
            return {
                "tx_hash": tx_hash,
                "status": "SUCCESS" if status == "0x1" else "FAILED" if status == "0x0" else "PENDING",
                "is_verified": status is not None
            }
        except Exception as e:
            return {"tx_hash": tx_hash, "status": "UNKNOWN", "is_verified": False, "error": str(e)}

    def enforce_truth_rule(self, claim: str, verification_result: dict) -> str:
        success_keywords = ["สำเร็จ", "Success", "✅", "DONE", "Confirmed"]
        has_success_claim = any(kw in claim for kw in success_keywords)
        if has_success_claim and not verification_result.get('is_verified', False):
            return f"⛔ TRUTH VIOLATION DETECTED: Claimed success but verification failed.\nOriginal: {claim}\nCORRECTED: การดำเนินการล้มเหลวหรือยังไม่ได้รับการยืนยันจากแหล่งข้อมูลจริง"
        return claim

    def log_correction(self, original_claim: str, corrected_response: str, verification_result: dict):
        entry = {
            "timestamp": time.time(), "original_claim": original_claim,
            "corrected_response": corrected_response,
            "verification_result": verification_result,
            "correction_type": "UNVERIFIED_SUCCESS_CLAIM"
        }
        try:
            with open("truth_dataset.json", "r+", encoding="utf-8") as f:
                data = json.load(f); data.append(entry); f.seek(0); json.dump(data, f, ensure_ascii=False, indent=2)
        except FileNotFoundError:
            with open("truth_dataset.json", "w", encoding="utf-8") as f:
                json.dump([entry], f, ensure_ascii=False, indent=2)
        print(f"📝 Correction logged to truth_dataset.json")

if __name__ == "__main__":
    v = GroundTruthVerifier()
    print("✅ Truth Verifier Rebuilt Successfully with log_correction")
