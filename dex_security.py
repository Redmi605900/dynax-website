import hashlib
import json
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError

def verify_swap_signature(payload: dict, signature_hex: str, public_key_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        signature_bytes = bytes.fromhex(signature_hex)
        message = json.dumps(payload, sort_keys=True).encode('utf-8')
        return vk.verify(signature_bytes, message, hashfunc=hashlib.sha256)
    except (BadSignatureError, ValueError, TypeError) as e:
        print(f"Signature verification failed: {e}")
        return False
