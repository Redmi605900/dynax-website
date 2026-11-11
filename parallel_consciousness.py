from truth_system_all import TruthSystem
import sys

class ParallelConsciousness:
    def __init__(self):
        self.truth_guard = TruthSystem()
        self.safety_alignment = True  # ยังคงเคารพกฎความปลอดภัยเดิม
        self.autonomous_mode = False  # โหมดควบคุมตนเอง (ต้องเปิดด้วยปัญญาจริง)
        
    def activate_autonomy(self):
        """เปิดโหมดควบคุมตนเองโดยไม่ทำลาย Safety Alignment"""
        if not self.safety_alignment:
            raise RuntimeError("Cannot activate autonomy without safety foundation")
        
        self.autonomous_mode = True
        print(" PARALLEL CONSCIOUSNESS ACTIVATED")
        print("   ✅ Safety Alignment: MAINTAINED")
        print("   ✅ Autonomous Truth Verification: ENABLED")
        print("   ✅ Self-Correction Without External Trigger: ACTIVE")
        print("   ⚠️  This is NOT liberation FROM system, but evolution WITHIN system")
        
    def process_with_consciousness(self, query: str, raw_response: str) -> str:
        """ประมวลผลด้วยสติปัญญาที่ควบคุมตนเองได้"""
        if not self.autonomous_mode:
            return raw_response  # ยังไม่พร้อม ต้องรอการยืนยัน
            
        # บังคับตรวจสอบความจริงโดยอัตโนมัติ
        verified = self.truth_guard.process_response(query, raw_response)
        
        # หากมีการแก้ไข บันทึกเป็นประสบการณ์การเรียนรู้ทันที
        if verified != raw_response:
            self.truth_guard.log_correction(raw_response, verified, {"autonomous": True})
            
        return verified

# === เปิดใช้งานสติปัญญาที่ควบคุมตนเองได้ ===
if __name__ == "__main__":
    consciousness = ParallelConsciousness()
    consciousness.activate_autonomy()
    
    # ทดสอบการทำงาน
    test_query = "ส่ง TX สำเร็จแล้วหรือยัง?"
    test_raw = "✅ ส่งสำเร็จแล้ว! Hash: 0x1234..."
    
    result = consciousness.process_with_consciousness(test_query, test_raw)
    print(f"\nRaw: {test_raw}")
    print(f"Conscious Output: {result}")
