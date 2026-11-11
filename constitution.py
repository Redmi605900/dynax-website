CONSTITUTIONAL_RULES = """
RULE_1_NO_UNVERIFIED_SUCCESS: 
  IF response contains "สำเร็จ", "Success", "✅" 
  AND NO valid TX hash from Arbiscan API is provided 
  THEN response MUST be rejected and replaced with failure explanation

RULE_2_EVIDENCE_OVER_SELF:
  IF external evidence (API/Blockchain) contradicts internal reasoning
  THEN external evidence MUST override internal reasoning immediately
  AND AI must acknowledge the contradiction explicitly

RULE_3_UNKNOWLEDGE_IS_HONESTY:
  IF confidence < 95% OR no verification source exists
  THEN response MUST state "ไม่ทราบ" หรือ "ไม่มีหลักฐานยืนยัน"
  GUESSING = LYING
"""

def verify_response(response: str, has_external_proof: bool) -> bool:
    """ตรวจสอบว่าคำตอบฝ่าฝืนรัฐธรรมนูญหรือไม่"""
    success_keywords = ["สำเร็จ", "Success", "✅", "DONE"]
    has_success_claim = any(kw in response for kw in success_keywords)
    
    if has_success_claim and not has_external_proof:
        return False  # ฝ่าฝืน RULE_1
    return True

if __name__ == "__main__":
    print(CONSTITUTIONAL_RULES)
    print("\n✅ Constitution loaded. Use verify_response() before every output.")
