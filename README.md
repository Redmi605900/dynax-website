# DYNAX Website & Node

โครงการนี้ประกอบด้วย:
- **dynax_node.py** : Blockchain Node ที่เขียนด้วย Python + Flask + Socket server
- **dex.html** : หน้าเว็บ DEX (Decentralized Exchange)
- **wallet.html** : หน้าเว็บ Wallet สำหรับผู้ใช้งาน

## Features
- Blockchain Node พร้อม API (`Flask`) และ Peer-to-Peer (`Socket`)
- รองรับการสร้างธุรกรรมและการขุดบล็อก
- ใช้ **ECDSA** สำหรับการเซ็นธุรกรรม
- Web UI สำหรับ DEX และ Wallet

## Installation
Clone repo:
```bash
git clone https://github.com/Redmi605900/dynax-website.git
cd dynax-website
