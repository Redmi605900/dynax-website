# ติดตั้ง library ก่อน (ครั้งเดียว)
# pip install requests python-dotenv

import requests
import os
from dotenv import load_dotenv

# โหลดค่าจาก .env
load_dotenv()
render_url = os.getenv("RENDER_NODE_URL")
local_chain_path = os.getenv("LOCAL_CHAIN_PATH")

# อ่าน chain.json จาก local
with open(local_chain_path, "r") as f:
    chain_data = f.read()

# ส่ง chain.json ไป Render node
try:
    response = requests.post(
        f"{render_url}/upload-chain",
        data=chain_data,
        headers={"Content-Type": "application/json"}
    )
    if response.status_code == 200:
        print("✅ Chain synced successfully to Render node")
    else:
        print("❌ Sync failed:", response.status_code, response.text)
except Exception as e:
    print("⚠️ Error:", str(e))
