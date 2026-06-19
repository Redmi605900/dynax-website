# DYNAX Layer 1 Blockchain - Documentation

### Introduction

**DYNAX** is a Layer 1 Blockchain Platform with:
- Secure Wallet
- Proof of Work Mining
- P2P Network
- DEX (Decentralized Exchange)
- Smart Contracts (DVM)
- Block Explorer

**Technical Specs:**
- Native Coin: DYX
- Consensus: Proof of Work
- Block Time: ~30 seconds
- Mining Reward: 50 DYX/block

---

### API Reference

#### Blockchain Node (Port 6002)

**GET /blocks** - Get all blocks

**GET /balance/<address>** - Check balance

**POST /tx/send** - Send transaction

{}`
{
  "from": "DX...",
  "to": "DX...",
  "amount": 100,
  "fee": 0.01,
  "private_key": "..."
}
```

**GET /mine/<miner>** - Mine new block

---

#### DEX (Port 6004)

**POST /order** - Create order

```json
{
  "type": "buy",
  "price": 0.55,
  "amount": 100,
  "trader": "DX..."
}
```

**GET /orderbook** - Get order book

**GET /trades** - Get trade history

---

#### DVM Port 6005)

**POST /deploy** - Deploy contract

```json
{
  "creator": "DX...",
  "code": "def transfer(params):...",
  "state": {"balances": {...}}
}
```

**POST /execute** - Execute contract

```json
{
  "contract_id": "...",
  "function": "transfer",
  "params": {"sender": "...", "receiver": "...", "amount": 1000},
  "caller": "DX..."
}
```

---

### Smart Contracts Example

```python
def transfer(params):
    sender = params.get("sender")
    receiver = params.get("receiver")
    amount = params.get("amount", 0)
    
    if state["balances"].get(sender, 0) < amount:
        return {"error": "Insufficient balance"}
    
    state["balances"][sender] -= amount
    state["balances"][receiver] = state["balances"].get(receiver, 0) + amount
    
    return {"success": True}

def balance_of(params):
    address = params.get("address")
    return {"balance": state["balances"].get(address, 0)}
```

---

### Access Points

- **Block Explorer:** http://localhost:6006
- **Mobile App:** http://localhost:6007
- **DEX:** http://localhost:6004
- **DVM API:** http://localhost:6005
- **Node 1:** http://localhost:6002
- **Node 2:** http://localhost:6003

---

**DYNAX - Layer 1 Blockchain Platform**