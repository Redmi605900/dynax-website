import hashlib
import secrets

# secp256k1: ใช้เฉพาะการทดสอบในเครื่อง
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)

def inv(a, m):
    return pow(a % m, -1, m)

def add(A, B):
    if A is None:
        return B
    if B is None:
        return A
    x1, y1 = A
    x2, y2 = B
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if A == B:
        slope = (3 * x1 * x1) * inv(2 * y1, P) % P
    else:
        slope = (y2 - y1) * inv(x2 - x1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    y3 = (slope * (x1 - x3) - y1) % P
    return x3, y3

def mul(k, point=G):
    result = None
    current = point
    k %= N
    while k:
        if k & 1:
            result = add(result, current)
        current = add(current, current)
        k >>= 1
    return result

def hash_int(message):
    return int.from_bytes(hashlib.sha256(message).digest(), "big") % N

def sign(z, d, k):
    R = mul(k)
    r = R[0] % N
    s = inv(k, N) * (z + r * d) % N
    if r == 0 or s == 0:
        raise ValueError("Invalid test signature")
    return r, s

def verify(z, signature, Q):
    r, s = signature
    if not (1 <= r < N and 1 <= s < N):
        return False
    w = inv(s, N)
    point = add(mul(z * w % N), mul(r * w % N, Q))
    return point is not None and point[0] % N == r

def recover_if_same_nonce(z1, sig1, z2, sig2):
    r1, s1 = sig1
    r2, s2 = sig2
    if r1 != r2:
        return None
    # สูตรสำหรับลายเซ็นที่ใช้ nonce เดิมและค่า s ตามที่เซ็นไว้
    k = (z1 - z2) * inv(s1 - s2, N) % N
    d = (s1 * k - z1) * inv(r1, N) % N
    return d

def run_case(reuse_nonce):
    d = secrets.randbelow(N - 1) + 1
    Q = mul(d)
    z1 = hash_int(b"local audit message A")
    z2 = hash_int(b"local audit message B")

    k1 = secrets.randbelow(N - 1) + 1
    k2 = k1 if reuse_nonce else secrets.randbelow(N - 1) + 1

    sig1 = sign(z1, d, k1)
    sig2 = sign(z2, d, k2)

    valid = verify(z1, sig1, Q) and verify(z2, sig2, Q)
    same_r = sig1[0] == sig2[0]
    recovered = recover_if_same_nonce(z1, sig1, z2, sig2) if same_r else None

    # ECDSA มีความกำกวมจาก s กับ -s mod N;
    # ตรวจทั้งสองตัวเลือกเพื่อให้การทดสอบไม่พลาดกรณี low-s/high-s
    recovered_ok = recovered == d
    if recovered is not None and not recovered_ok:
        recovered_ok = ((-recovered) % N) == d

    print("\nCASE:", "REUSED NONCE" if reuse_nonce else "INDEPENDENT NONCES")
    print("SIGNATURES_VALID:", valid)
    print("R_VALUES_EQUAL:", same_r)
    print("RECOVERY_ATTEMPTED:", recovered is not None)
    print("TEST_KEY_MATCH:", recovered_ok)
    return valid, same_r, recovered_ok

print("ECDSA SECP256K1 LOCAL TEST")
print("No network, wallet files, or real addresses used.")

normal = run_case(False)
vulnerable = run_case(True)

print("\nSUMMARY")
print("NORMAL_SIGNATURES_VALID:", normal[0])
print("NORMAL_NONCE_NOT_REUSED:", not normal[1])
print("REUSED_NONCE_DETECTED:", vulnerable[1])
print("TEST_KEY_RECOVERY_VERIFIED:", vulnerable[2])

passed = (
    normal[0]
    and not normal[1]
    and vulnerable[0]
    and vulnerable[1]
    and vulnerable[2]
)
print("ALL_TESTS_PASS:", passed)
