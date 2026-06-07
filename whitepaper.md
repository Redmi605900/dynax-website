DYNAX (DYX) — Whitepaper v1.0
Version: 1.0.0
Date: June 2026
Author: Hideko Nanoura
Website: dynax-website.vercel.app
Network: Mainnet (Chain ID: 1337)
Abstract
DYNAX (ticker: DYX) is a decentralized Layer 1 blockchain designed for peer-to-peer digital payments without intermediaries. Inspired by Bitcoin's core principles, DYNAX introduces quantum-resistant cryptographic hashing via SHA3-256, ensuring long-term security against emerging quantum computing threats. The network operates through Proof-of-Work consensus, allowing anyone to participate as a node operator or miner without permission.
1. Introduction
The global financial system relies on centralized intermediaries — banks, payment processors, and governments — to validate and record transactions. This creates systemic risks: censorship, single points of failure, and exclusion of unbanked populations.
DYNAX eliminates these intermediaries by providing:
A fully decentralized peer-to-peer payment network
Cryptographic security resistant to quantum computing attacks
An open, permissionless protocol anyone can join
2. Technical Specifications
Parameter
Value
Ticker
DYX
Algorithm
Proof-of-Work (SHA3-256)
Block Time
~12 seconds
Initial Block Reward
50 DYX
Halving Interval
Every 210,000 blocks
Maximum Supply
11,000,000 DYX
Network ID
1337
Protocol Version
2.5.0
Address Prefix
DX
Signature Scheme
ECDSA (secp256k1)
Address Format
DX + SHA3-256(public_key)[:40]
Difficulty Adjustment
Every 10 blocks
Target Block Time
12 seconds
3. Why SHA3-256?
Bitcoin uses SHA2-256, which faces theoretical vulnerabilities from Grover's algorithm on quantum computers, effectively halving the security level from 256-bit to 128-bit.
DYNAX uses SHA3-256 (Keccak) which offers:
Superior resistance to quantum attacks
Different internal structure (sponge construction) vs SHA2
No known length-extension vulnerabilities
NIST FIPS 202 standardized
This makes DYNAX's block hashing and address generation more future-proof than first-generation cryptocurrencies.
4. Consensus Mechanism
DYNAX uses Proof-of-Work — the same battle-tested mechanism as Bitcoin.
How it works:
Miners collect pending transactions from the mempool
Miners compete to find a nonce such that SHA3-256(block) starts with N zeros
The first miner to find a valid hash broadcasts the block to the network
All nodes verify and accept the longest valid chain
Difficulty Adjustment:
Difficulty adjusts every 10 blocks to maintain the 12-second target block time.
5. Address System
DYNAX addresses are derived from ECDSA public keys using SHA3-256:
Code
This ensures:
Addresses are compact (42 characters)
Public keys are never exposed until a transaction is signed
Address derivation is quantum-resistant via SHA3-256
6. Transaction Model
Every transaction requires:
from: sender address
to: recipient address
amount: DYX amount
public_key: sender's ECDSA public key
signature: ECDSA signature of the transaction
The network verifies:
public_key matches the sender's address (via SHA3-256)
ECDSA signature is valid
Sender has sufficient balance
Transaction is not a double-spend
7. Supply Schedule
Total maximum supply: 11,000,000 DYX
Halving
Block Range
Reward
0
0 - 209,999
50 DYX
1
210,000 - 419,999
25 DYX
2
420,000 - 629,999
12.5 DYX
3
630,000 - 839,999
6.25 DYX
Genesis allocation: 307,582 DYX (pre-mined for development)
8. Network Architecture
DYNAX operates as a fully peer-to-peer network:
Any node can join by connecting to existing peers
Nodes share blocks and transactions via gossip protocol
Longest valid chain wins (Nakamoto consensus)
No central server or authority
Node Software:
Written in Python/Flask
Runs on any platform including Android (Termux)
Open source on GitHub
9. Roadmap
Phase 1 — Foundation (Completed)
Core blockchain (PoW, SHA3-256)
P2P network with consensus
ECDSA wallet system
Block explorer
Difficulty adjustment
Halving logic
Phase 2 — Network (In Progress)
Permanent 24/7 node infrastructure
Multiple independent node operators
Peer discovery automation
Phase 3 — Ecosystem
Web-based wallet
DEX (Decentralized Exchange)
Mobile wallet app
Developer documentation
Phase 4 — Community
Public launch
Exchange listings
Community governance
10. Getting Started
Run a Node:
Bash
Create a Wallet:
Bash
Explore the Network:
Visit: dynax-website.vercel.app/explorer.html
11. Conclusion
DYNAX represents a new generation of peer-to-peer digital currency combining Bitcoin's proven decentralization model with quantum-resistant cryptography. Built from the ground up with modern security standards, DYNAX aims to provide a censorship-resistant, permissionless payment network for the long term.
The network is open to all. Anyone can mine, run a node, or build on top of DYNAX.
This whitepaper is a living document and will be updated as the protocol evolves.
GitHub: github.com/Redmi605900
Explorer: dynax-website.vercel.app/explorer.html
Telegram: @QChainOfficial
Twitter/X: @QChainOfficial
12. Problem Statement
The Problem with Centralized Finance
Modern financial systems suffer from fundamental flaws:
Censorship — Banks can freeze accounts, block transactions, or deny service without recourse
Single Points of Failure — Centralized servers can be hacked, go offline, or be seized
Inflation — Central banks can print unlimited money, devaluing savings
Exclusion — 1.4 billion adults worldwide remain unbanked
Privacy — Every transaction is monitored, recorded, and subject to surveillance
Quantum Threat — Most existing blockchains use SHA2-256, which faces long-term vulnerability to quantum computing
The DYNAX Solution
DYNAX addresses each of these problems:
Problem
DYNAX Solution
Censorship
No authority can block transactions
Single point of failure
Fully distributed P2P network
Inflation
Hard cap of 11,000,000 DYX
Exclusion
Anyone with internet can participate
Privacy
Pseudonymous addresses
Quantum threat
SHA3-256 hashing throughout
13. Tokenomics
Total Supply Distribution
Allocation
Amount
Percentage
Mining Rewards
10,692,418 DYX
97.2%
Genesis (Development)
307,582 DYX
2.8%
Total
11,000,000 DYX
100%
Key Properties:
No pre-sale — No ICO, no private sale, no VC allocation
No team tokens — Development allocation is transparent and on-chain
Fair launch — Anyone can mine from block #1
Deflationary — Supply is strictly capped, reward halves every 210,000 blocks
Predictable — Emission schedule is hardcoded and immutable
Emission Schedule:
Total blocks to mine all rewards: ~22,000,000 blocks (~8.3 years at 12s/block)
14. Security Analysis
Proof-of-Work Security
DYNAX uses SHA3-256 Proof-of-Work which provides:
51% Attack Resistance:
An attacker would need to control more than 50% of the total network hash rate to rewrite history. As the network grows and more miners join, this becomes increasingly expensive and impractical.
Double-Spend Protection:
The node software enforces:
TXID uniqueness check in mempool
TXID uniqueness check in chain history
Balance validation including pending transactions
ECDSA signature verification on every transaction
Chain Validation:
Every node independently validates:
Hash continuity (prev_hash linkage)
Proof-of-Work validity (correct number of leading zeros)
ECDSA signatures on all transactions
Balance sufficiency
Quantum Resistance
SHA3-256 vs SHA2-256:
Property
SHA2-256
SHA3-256
Construction
Merkle-Damgard
Sponge (Keccak)
Quantum resistance
~128-bit (Grover)
~128-bit+
Length extension
Vulnerable
Immune
NIST standard
FIPS 180-4
FIPS 202
Used in Bitcoin
Yes
No
Used in DYNAX
No
Yes
SHA3-256's sponge construction provides additional security properties not present in SHA2-256, making it the preferred choice for long-term security.
ECDSA on secp256k1:
While ECDSA is theoretically vulnerable to Shor's algorithm on a sufficiently powerful quantum computer, practical quantum computers capable of breaking 256-bit elliptic curve cryptography are estimated to be decades away. DYNAX's roadmap includes migration to post-quantum signature schemes when the threat becomes practical.
15. Comparison with Existing Blockchains
Feature
Bitcoin
Litecoin
DYNAX
Hash Algorithm
SHA2-256
Scrypt
SHA3-256
Block Time
~10 min
~2.5 min
~12 sec
Max Supply
21M BTC
84M LTC
11M DYX
Halving Interval
210,000
840,000
210,000
Address Scheme
Base58
Base58
DX + SHA3
Quantum Resistant Hash
No
No
Yes
Consensus
PoW
PoW
PoW
Decentralized
Yes
Yes
Yes
Open Source
Yes
Yes
Yes
Key Differentiators:
SHA3-256 — More future-proof than Bitcoin's SHA2-256
Fast blocks — 12 seconds vs Bitcoin's 10 minutes
Scarce supply — Only 11M DYX vs Bitcoin's 21M
Modern codebase — Built with current best practices
16. References
Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System
NIST FIPS 202 (2015). SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions
Bernstein, D.J. & Lange, T. (2017). Post-quantum cryptography
Johnson, D., Menezes, A., & Vanstone, S. (2001). The Elliptic Curve Digital Signature Algorithm (ECDSA)
Grover, L.K. (1996). A fast quantum mechanical algorithm for database search
Shor, P.W. (1994). Algorithms for quantum computation: discrete logarithms and factoring
Disclaimer
This whitepaper is for informational purposes only. DYNAX is an experimental open-source blockchain protocol. The developers make no guarantees regarding the value, stability, or future development of DYX. Participation in the DYNAX network is at your own risk.
DYNAX has no central authority, no company, and no team. It is a protocol — like Bitcoin — maintained by its community of users and developers.
"Vires in Numeris" — Strength in Numbers
