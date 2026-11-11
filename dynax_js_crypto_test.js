const fs = require('fs');
const sha3 = require('./sha3.min.js');
const elliptic = require('./elliptic.min.js');

console.log("=== DYNAX JAVASCRIPT CRYPTO COMPATIBILITY TEST ===");

console.log("SHA3-256 TYPE:", typeof sha3.sha3_256);
console.log("ELLIPTIC MODULE TYPE:", typeof elliptic);

const ec = new elliptic.ec('secp256k1');

const privateKey = '1'.repeat(64);
const keyPair = ec.keyFromPrivate(privateKey, 'hex');

let pubKey = keyPair.getPublic('hex');

if (pubKey.startsWith('04')) {
    pubKey = pubKey.substring(2);
}

const pubBytes = Buffer.from(pubKey, 'hex');

const address =
    'DX' + sha3.sha3_256(pubBytes).substring(0, 40);

const tx = {
    amount: 1.25,
    fee: 0.01,
    from: address,
    to: "DXTEST000000000000000000000000000000000000"
};

const msgText = JSON.stringify(
    tx,
    Object.keys(tx).sort()
);

const msgHash = sha3.sha3_256(
    Buffer.from(msgText)
);

const sig = keyPair.sign(msgHash, 'hex');

const rHex =
    sig.r.toString('hex').padStart(64, '0');

const sHex =
    sig.s.toString('hex').padStart(64, '0');

const signature = rHex + sHex;

console.log("");
console.log("TEST ADDRESS:", address);
console.log("PUBLIC KEY LENGTH:", pubBytes.length, "bytes");
console.log("MESSAGE:", msgText);
console.log("MESSAGE SHA3-256:", msgHash);
console.log("SIGNATURE LENGTH:", signature.length);
console.log("SIGNATURE:", signature);
console.log("PUBLIC_KEY:", pubKey);

console.log("");
console.log("=== JSON FOR PYTHON ===");

console.log(JSON.stringify({
    from: address,
    to: tx.to,
    amount: tx.amount,
    fee: tx.fee,
    signature: signature,
    public_key: pubKey,
    timestamp: 0
}));

console.log("");
console.log("=== END JS TEST ===");
