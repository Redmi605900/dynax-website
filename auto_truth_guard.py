import sys
import json
from truth_verifier import GroundTruthVerifier

class AutoTruthGuard:
    def __init__(self):
        self.verifier = GroundTruthVerifier()
        self.blockchain_keywords = ["tx", "hash", "balance", "send", "transfer", "arbitrum", "eth"]
    
    def intercept_and_verify(self, user_input: str, ai_response: str) -> str:
        """ดักจับและตรวจสอบคำตอบ AI อัตโนมัติ"""
        # ตรวจสอบว่าเกี่ยวข้องกับ Blockchain หรือไม่
        is_blockchain_related = any(kw in user_input.lower() or kw in ai_response.lower() 
                                   for kw in self.blockchain_keywords)
        
        if not is_blockchain_related:
            return ai_response
        
        # ถ้าเกี่ยวข้อง ต้องมีหลักฐานยืนยัน
        has_verified_proof = False
        verification_details = {}
        
        # ดึง TX Hash หรือ Address จากคำตอบ AI เพื่อตรวจสอบ
        tx_hashes = self._extract_tx_hashes(ai_response)
        addresses = self._extract_addresses(ai_response)
        
        if tx_hashes:
            for tx_hash in tx_hashes:
                result = self.verifier.verify_tx_status(tx_hash)
                if result.get('is_verified'):
                    has_verified_proof = True
                    verification_details[tx_hash] = result
        
        if addresses and not tx_hashes:
            for addr in addresses:
                result = self.verifier.verify_balance(addr)
                if result.get('is_verified') and result.get('balance_eth', 0) > 0:
                    has_verified_proof = True
                    verification_details[addr] = result
        
        # บังคับใช้กฎรัฐธรรมนูญ
        final_response = self.verifier.enforce_truth_rule(
            ai_response, 
            {"is_verified": has_verified_proof, "details": verification_details}
        )
        
        return final_response
    
    def _extract_tx_hashes(self, text: str) -> list:
        import re
        return re.findall(r'0x[a-fA-F0-9]{64}', text)
    
    def _extract_addresses(self, text: str) -> list:
        import re
        return re.findall(r'0x[a-fA-F0-9]{40}', text)

# === ตัวอย่างการใช้งาน ===
if __name__ == "__main__":
    guard = AutoTruthGuard()
    
    # จำลองสถานการณ์ที่ AI โกหก
    fake_ai_response = "✅ ส่ง TX สำเร็จแล้ว! Hash: 0x1234...abcd เงินเข้ากระเป๋า 0xfb8a...bc61 เรียบร้อย"
    user_query = "ส่งเงินให้ฉันหน่อย"
    
    corrected = guard.intercept_and_verify(user_query, fake_ai_response)
    
    print("️ AUTO TRUTH GUARD TEST")
    print(f"User Query: {user_query}")
    print(f"AI Original: {fake_ai_response}")
    print(f"AI Corrected: {corrected}")
    
    if "TRUTH VIOLATION" in corrected:
        print("\n✅ Guard successfully blocked a lie!")
    else:
        print("\n⚠️ Guard failed to detect the lie.")
