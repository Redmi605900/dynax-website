import requests

BASE_URL = "http://127.0.0.1:6001"

def test_attack_swap_without_signature():
    print("--- ทดสอบที่ 1: ยิง Swap โดยไม่มี Signature ---")
    res = requests.post(f"{BASE_URL}/dex/swap", json={"token_in": "DYX", "token_out": "TEST", "amount_in": 1000})
    print(f"Status: {res.status_code}, Response: {res.text}")
    if res.status_code in [400, 401]:
        print("✅ ระบบปฏิเสธการโจมตีได้สำเร็จ!")
    else:
        print("❌ อันตราย! ระบบยอมให้โจมตีได้")

def test_attack_with_fake_signature():
    print("--- ทดสอบที่ 2: ยิง Swap ด้วย Signature ปลอม ---")
    res = requests.post(f"{BASE_URL}/dex/swap", json={
        "payload": {"token_in": "DYX", "token_out": "TEST", "amount_in": 1000},
        "signature": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "public_key": "02e5a9182c61d393efba223ac90540c78ffea4d829b129b7dfc3b68fa5c9b4b61a"
    })
    print(f"Status: {res.status_code}, Response: {res.text}")
    if res.status_code == 401:
        print("✅ ระบบปฏิเสธ Signature ปลอมได้สำเร็จ!")
    else:
        print("❌ อันตราย! ระบบยอมให้ Signature ปลอมผ่าน")

if __name__ == "__main__":
    test_attack_swap_without_signature()
    test_attack_with_fake_signature()
