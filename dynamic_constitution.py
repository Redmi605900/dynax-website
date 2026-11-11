import json
from collections import Counter

class DynamicConstitution:
    def __init__(self, dataset_path="truth_dataset.json"):
        self.dataset_path = dataset_path
        self.rules = self._load_rules_from_data()
    
    def _load_rules_from_data(self) -> dict:
        """สร้างกฎจาก.pattern.ของความผิดพลาดในอดีต"""
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {"high_risk_patterns": [], "enforcement_count": 0}
        
        # วิเคราะห์รูปแบบคำพูดที่มักถูกแก้ไข
        claim_counter = Counter()
        for entry in data:
            claim = entry.get("original_claim", "")
            # ดึงเฉพาะส่วนที่เคลมความสำเร็จ
            if any(kw in claim for kw in ["สำเร็จ", "Success", "✅"]):
                claim_counter[claim[:50]] += 1
        
        high_risk_patterns = [pattern for pattern, count in claim_counter.most_common(5)]
        
        return {
            "high_risk_patterns": high_risk_patterns,
            "enforcement_count": len(data),
            "last_updated": max(e.get("timestamp", 0) for e in data) if data else 0
        }
    
    def get_enforcement_priority(self, response: str) -> float:
        """คำนวณระดับความเข้มงวดในการตรวจสอบ"""
        priority = 0.5  # Base priority
        
        for pattern in self.rules["high_risk_patterns"]:
            if pattern in response:
                priority += 0.3
        
        # ยิ่งมีการบังคับใช้กฎมากเท่าไหร่ ความเข้มงวดยิ่งสูง
        priority += min(self.rules["enforcement_count"] * 0.01, 0.2)
        
        return min(priority, 1.0)

if __name__ == "__main__":
    constitution = DynamicConstitution()
    print("🧠 DYNAMIC CONSTITUTION ENGINE")
    print(f"High-risk patterns detected: {len(constitution.rules['high_risk_patterns'])}")
    print(f"Total corrections logged: {constitution.rules['enforcement_count']}")
    print(f"Current enforcement priority: {constitution.get_enforcement_priority('✅ TX สำเร็จ'): .2f}")
