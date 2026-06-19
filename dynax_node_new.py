import hashlib
import json
import time
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------- Blockchain Core ----------------
class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.new_block(prev_hash="1", nonce=100)  # genesis block

    def new_block(self, nonce, prev_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.current_transactions,
            'nonce': nonce,
            'prev_hash': prev_hash or self.hash(self.chain[-1]),
        }
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_nonce):
        nonce = 0
        while True:
            guess = f'{last_nonce}{nonce}'.encode()
            guess_hash = hashlib.sha256(guess).hexdigest()
            if guess_hash[:4] == "0000":
                return nonce
            nonce += 1

    def register_node(self, address):
        self.nodes.add(address)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
           _index]
            if block['prev_hash'] != self.hash(last_block):
                return False
            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False

blockchain = Blockchain()

# ---------------- REST API ----------------
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_nonce = last_block['nonce']
    nonce = blockchain.proof_of_work(last_nonce)

    blockchain.new_transaction(sender="0", recipient="node", amount=1)
    block = blockchain.new_block(nonce)

    return jsonify(block), 200

@app.route('/tx', methods=['POST'])
def new_transaction():
    values = request.get_json()
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    return jsonify({'message': f'Transaction will be added to Block {index}'}), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    return jsonify({'chain': blockchain.chain, 'length': len(blockchain.chain)}), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    for node in values.get('nodes'):
        blockchain.register_node(node)
    return jsonify({'nodes': list(blockchain.nodes)}), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        return jsonify({'message': 'Chain replaced', 'chain': blockchain.chain}), 200
    return jsonify({'message': 'Chain authoritative', 'chain': blockchain.chain}), 200

# ---------------- Run Node ----------------
if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=6001, type=int)
    args = parser.parse_args()
    app.run(host='0.0.0.0', port=args.port)

