# DYNAX Layer 1 Blockchain - API Documentation

## 📖 Overview
DYNAX is a Layer 1 blockchain with native coin DYX, smart contracts, and DEX.

## 🔗 Network Info
- **Node URL:** http://127.0.0.1:6002
- **DEX URL:** http://127.0.0.1:6004
- **DVM URL:** http://127.0.0.1:6005
- **Explorer URL:** http://127.0.0.1:6006

---

## 📦 Blockchain API (Port 6002)

### Get All Blocks
```bash
GET /blocks
```
**Response:**
```json
[
  {
    "index": 0,
    "timestamp": 1781759886,
    "transactions": [],
    "prev_hash": "0000...",
    "hash": "0000abc...",
    "nonce": 0
  }
]
```

### Get Balance
```bash
GET /balance/<address>
```
**Response:**
```json
{
  "address": "DXa5ae9ccc...",
  "balance": 300575.0
}
```

### Send Transaction
```bash
POST /tx/send
Content-Type: application/json
{
  "from": "DXa5ae9ccc...",
  "to": "DXd02527f0...",
  "amount": 100,
  "fee": 0.01,
  "private_key": "your_private_key"
}
```

### Mine Block
```bash
GET /mine/<miner_address>
```
**Response:**
```json
{
  "block": 24,
  "status": "mined"
}
```

### Add Peer
```bash
POST /peers/add
Content-Type: application/json

{
  "peer": "http://127.0.0.1:6003"
}
```

---

## 💱 DEX API (Port 6004)

### Place Order
```bash
POST /order
Content-Type: application/json

{
  "type": "buy",
  "price": 0.55,
  "amount": 100,
  "trader": "DXa5ae9ccc..."
}
```

### Get Order Book```bash
GET /orderbook
```

### Get Trades
```bash
GET /trades
```

### Get Price
```bash
GET /price
```

---

## 🧠 Smart Contracts API (Port 6005)

### Deploy Contract
```bash
POST /deploy
Content-Type: application/json

{
  "creator": "DXa5ae9ccc...",
  "code": "def increment(params):\n    state[\"count\"] += 1\n    return state[\"count\"]",
  "state": {"count": 0}
}
```

### Execute Contract
```bash
POST /execute
Content-Type: application/json

{
  "contract_id": "ffac6dbe8a7b6f4375f6",
  "function": "increment",
  "params": {},
  "caller": "DXa5ae9ccc..."
}
```

### Get Contracts
```bash
GET /contracts
```

---
## 📝 Examples

### Python Example - Send DYX
```python
import requests

# Send DYX
tx = {
    "from": "DXa5ae9ccc...",
    "to": "DXd02527f0...",
    "amount": 100,
    "fee": 0.01,
    "private_key": "your_key"
}

response = requests.post("http://127.0.0.1:6002/tx/send", json=tx)
print(response.json())
```

### JavaScript Example - Get Balance
```javascript
const address = "DXa5ae9ccc...";
fetch(`http://127.0.0.1:6002/balance/${address}`)
  .then(res => res.json())
  .then(data => console.log(data.balance));
```

---

## 🔐 Security
- Always use HTTPS in production
- Never expose private keys
- Use environment variables for sensitive data
- Implement rate limiting

---

## 📞 Support
For questions and support, contact: dynax-support@example.com
