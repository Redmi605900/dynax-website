# DYNAX — Layer 1 Blockchain

DYNAX (ticker: **DYX**) คือบล็อกเชน Layer 1 แบบ Proof-of-Work ที่พัฒนาขึ้นตั้งแต่ศูนย์ **จากโทรศัพท์มือถือเครื่องเดียว** ผ่าน Termux โดยไม่มีเซิร์ฟเวอร์ ไม่มีทีมงาน และไม่มีเงินทุนสนับสนุน

## เกี่ยวกับโปรเจกต์นี้

DYNAX ไม่ได้ตั้งใจแข่งขันหรือเทียบชั้นกับ Bitcoin หรือบล็อกเชนขนาดใหญ่ที่มี node นับหมื่นและผ่านการทดสอบความปลอดภัยมาหลายปี เป้าหมายของเราคือการสร้างระบบที่ทำงานได้จริง โปร่งใส และพัฒนาอย่างมีความรับผิดชอบทีละขั้นตอน

เราเชื่อในหลักการกระจายศูนย์ (decentralization) อย่างจริงจัง ไม่มีฟีเจอร์ใดที่เอื้อประโยชน์ให้ผู้พัฒนาฝ่ายเดียว ทุกคนที่รัน node ของตัวเองมีสิทธิ์เท่าเทียมกัน

## Technical Specs

- Consensus: Proof-of-Work (SHA3-256)
- Ticker: DYX
- Max Supply: 11,000,000 DYX
- Block Reward: 50 DYX (พร้อมกลไก halving)
- Difficulty: ปรับอัตโนมัติตามเวลาขุดเฉลี่ย

## โครงสร้างโปรเจกต์

- dynax_node_v20.py - Node หลัก (Flask API + P2P sync + mining)
- run_both.py - รวม node เข้ากับหน้าเว็บ (landing, dashboard, wallet, explorer)
- dashboard.html, explorer.html, landing.html, wallet.html - หน้าเว็บ UI
- watchdog.sh - ระบบ auto-recovery สำหรับ node, tunnel, และ mining
- automine_loop.sh - สคริปต์ขุดอัตโนมัติ

## Security

โปรเจกต์นี้ผ่านการตรวจสอบและแก้ไขช่องโหว่ด้านความปลอดภัยอย่างต่อเนื่อง รวมถึง

- Signature verification แบบเข้มงวดสำหรับทุกธุรกรรม
- การป้องกัน double-spending ผ่านการตรวจสอบยอดคงเหลือก่อนรับบล็อก
- Rate limiting สำหรับ endpoint ที่เกี่ยวข้องกับการปลดล็อก wallet
- ไม่มี hardcoded credentials หรือ backdoor ใดๆ ในโค้ด

หมายเหตุ: นี่เป็นโปรเจกต์ที่อยู่ระหว่างการพัฒนา (early-stage) ยังไม่ผ่านการตรวจสอบโดยนักวิจัยความปลอดภัยภายนอก ผู้ใช้ควรเข้าใจความเสี่ยงก่อนใช้งานจริง

## Installation

git clone https://github.com/Redmi605900/dynax-website.git
cd dynax-website
pip install -r requirements.txt
python3 run_both.py

## API Endpoints (บางส่วน)

- GET /chain - ดูเชนทั้งหมด
- GET /balance/<address> - เช็คยอดคงเหลือ
- GET /mine/<miner_address> - ขุดบล็อกใหม่
- POST /tx/send - ส่งธุรกรรม
- GET /peers - ดูรายชื่อ peer ที่เชื่อมต่ออยู่

## สถานะปัจจุบัน

โปรเจกต์นี้ยังคงพัฒนาอย่างต่อเนื่อง ทุกการเปลี่ยนแปลงถูกบันทึกไว้อย่างโปร่งใสผ่าน git history
