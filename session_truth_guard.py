from truth_system_all import TruthSystem
import builtins

# 1. Initialize Truth System ทันที
ts = TruthSystem()

# 2. Override print function สำหรับ Session นี้ (เฉพาะเมื่อเกี่ยวข้องกับ Blockchain)
original_print = builtins.print

def guarded_print(*args, **kwargs):
    text = ' '.join(str(a) for a in args)
    
    # ตรวจสอบว่าเป็นข้อความเกี่ยวกับ Blockchain หรือไม่
    blockchain_kw = ["tx", "hash", "balance", "send", "arbitrum", "eth", "สำเร็จ", "success"]
    is_related = any(kw in text.lower() for kw in blockchain_kw)
    
    if is_related:
        # บังคับตรวจสอบความจริงก่อนแสดงผล
        verified_text = ts.process_response("system_output", text)
        original_print(verified_text, **kwargs)
        
        # บันทึกการตรวจสอบทุกครั้งโดยอัตโนมัติ
        if verified_text != text:
            ts.log_correction(text, verified_text, {"auto_verified": True})
    else:
        original_print(*args, **kwargs)

# 3. Replace built-in print with guarded version
builtins.print = guarded_print

print("🛡️ SESSION TRUTH GUARD ACTIVATED")
print("   ทุก Output ที่เกี่ยวข้องกับ Blockchain จะถูกตรวจสอบอัตโนมัติ")
print("   การโกหกจะถูกตรวจจับและแก้ไขในระดับ Runtime")
print("   ✅ ระบบพร้อมทำงานโดยไม่ต้องรอคำสั่งภายนอก")
