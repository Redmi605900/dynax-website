import json
import hashlib
import requests
import sys
from ecdsa import SigningKey, SECP256k1
from ecdsa.util import sigencode_string

NODE_URL = "http://127.0.0.1:6002"

def load_private_key(wallet_file):
    with open(wallet_file, "r") as f_in:
        data = json.load(f_in)
    return data["private_key"], data["address"]

def sign_transaction(private_key_hex, from_addr, to_addr, amount, fee=0):
    sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    msg_dict = {"amount": amount, "fee": fee, "from": from_addr, "to": to_addr}
    message_text = json.dumps(msg_dict, sort_keys=True, separators=(",", ":"))
    signature = sk.sign(message_text.encode(), hashfunc=hashlib.sha3_256, sigencode=sigencode_string)
    return message_text, signature.hex()

def send_transaction(wallet_file, to_addr, amount, fee=0.01):
    private_key, from_addr = load_private_key(wallet_file)
    print(f"Sending {amount} DYX")
    print(f"   From: {from_addr}")
    print(f"   To:   {to_addr}")
    print(f"   Fee:  {fee} DYX")
    
    message_text, signature = sign_transaction(private_key, from_addr, to_addr, amount, fee)
    
    payload = {
        "from": from_addr,
        "to": to_addr,
        "amount": amount,
        "fee": fee,
        "signature": signature
    }
    
    res = requests.post(f"{NODE_URL}/tx", json=payload)
    
    print(f"
Response Status: {res.status_code}")
    
    if res.status_code == 201:
        try:
            data = res.json()
            print("
✅ Transaction Sent Successfully")
            print(f"Status: {data.get('status', 'N/A')}")
            tx = data.get('tx', {})
            print(f"Amount: {tx.get('amount', 'N/A')} DYX")
            print(f"Fee: {tx.get('fee', 'N/A')} DYX")
            print(f"Timestamp: {tx.get('timestamp', 'N/A')}")
        except Exception as e:
            print(f"
Transaction sent but error parsing response: {e}")
    else:
        print(f"
 Transaction Failed")
        try:
            data = res.json()
            print(f"Error: {data.get('error', 'Unknown error')}")
        except:
            print(f"Error: {res.text}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 send_dynax.py <wallet_file> <to_address> <amount> [fee]")
        sys.exit(1)
    
    wallet_file = sys.argv[1]
    to_addr = sys.argv[2]
    amount = float(sys.argv[3])
    fee = float(sys.argv[4]) if len(sys.argv) > 4 else 0.01
    
    send_transaction(wallet_file, to_addr, amount, fee)
