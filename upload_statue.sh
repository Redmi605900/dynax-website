#!/data/data/com.termux/files/usr/bin/bash
# สคริปต์อัปโหลดรูปไปยัง dynax-website บน Vercel

# 1. เข้าไปที่โปรเจกต์
cd ~/dynax-website || exit

# 2. สร้างโฟลเดอร์ public ถ้ายังไม่มี
mkdir -p public

# 3. ย้ายรูปจาก Downloads ไปยัง public/
mv ~/storage/downloads/satoshi_statue_d.jpeg public/

# 4. เพิ่มโค้ด HTML ให้แสดงรูปใน index.html
# (ถ้า index.html มีอยู่แล้ว จะเพิ่มบรรทัดนี้ท้ายไฟล์)
echo '<img src="/satoshi_statue_d.jpeg" alt="รูปปั้นสื่อถึงมูลค่า" width="400">' >> index.html

# 5. Commit และ push ขึ้น GitHub
git add .
git commit -m "เพิ่มรูปปั้นสัญลักษณ์ Đ ลงเว็บไซต์"
git push origin main

# 6. แจ้งผล
echo "✅ รูปถูกเพิ่มและ push ไปยัง GitHub แล้ว Vercel จะ deploy อัตโนมัติ"
