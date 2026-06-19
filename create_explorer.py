code = '''import json
import time
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
NODE_URL = "http://127.0.0.1:6002"
DVM_URL = "http://127.0.0.1:6005"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DYNAX Block Explorer</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
body { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); min-height: 100vh; color: white; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { text-align: center; margin-bottom: 30px; padding: 20px; background: rgba(247,147,26,0.1); border-radius: 20px; border: 2px solid rgba(247,147,26,0.3); }
.header h1 { color: #F7931A; font-size: 32px; margin-bottom: 10px; }
.header p { color: #888; font-size: 14px; }
.search-box { margin: 20px 0; }
.search-box input { width: 100%; padding: 15px; border: 2px solid rgba(247,147,26,0.3); border-radius: 10px; background: rgba(0,0,0,0.3); color: white; font-size: 16px; }
.search-box button { width: 100%; padding: 15px; border: none; border-radius: 10px; background: linear-gradient(135deg, #F7931A, #FFA500); color: white; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 10px; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
.stat-card { background: rgba(247,147,26,0.1); border: 2px solid rgba(247,147,26,0.3); border-radius: 15px; padding: 20px; text-align: center; }
.stat-card h3 { color: #F7931A; font-size: 14px; margin-bottom: 10px; }
.stat-card .value { font-size: 28px; font-weight: bold; color: white; }
.tabs { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; }
.tab { padding: 12px 24px; background: rgba(247,147,26,0.1); border: 2px solid rgba(247,147,26,0.3); border-radius: 10px; cursor: pointer; color: white; font-weight: 600; }
.tab.active { background: linear-gradient(135deg, #F7931A, #FFA500); border-color: #F7931A; }
.content { background: rgba(0,0,0,0.3); border-radius: 15px; padding: 20px; margin: 20px 0; }
.block-item, .tx-item, .contract-item { background: rgba(247,147,26,0.05); border: 1px solid rgba(247,147,26,0.2); border-radius: 10px; padding: 15px; margin: 10px 0; }
.block-item:hover, .tx-item:hover, .contract-item:hover { background: rgba(247,147,26,0.1); }
.block-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.block-number { font-size: 20px; font-weight: bold; color: #F7931A; }
.block-hash { font-size: 12px; color: #888; font-family: monospace; word-break: break-all; }
.tx-list { margin-top: 10px; }
.tx-item { font-size: 14px; padding: 10px; }
.label { color: #888; font-size: 12px; }
.value-highlight { color: #F7931A; font-weight: bold; }
.loading { text-align: center; padding: 40px; color: #888; }
.error { color: #FF3B30; text-align: center; padding: 20px; }
@media (max-width: 768px) {
    .header h1 { font-size: 24px; }
    .stat-card .value { font-size: 22px; }
}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🔶 DYNAX Block Explorer</h1>
        <p>Layer 1 Blockchain Explorer</p>
    </div>
    
    <div class="search-box">
        <input type="text" id="search" placeholder="Search by Block Number, Hash, or Address...">
        <button onclick="search()">🔍 Search</button>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>Total Blocks</h3>
            <div class="value" id="total-blocks">-</div>
        </div>
        <div class="stat-card">
            <h3>Total Transactions</h3>
            <div class="value" id="total-txs">-</div>
        </div>
        <div class="stat-card">
            <h3>Smart Contracts</h3>
            <div class="value" id="total-contracts">-</div>
        </div>
        <div class="stat-card">
            <h3>Network Status</h3>
            <div class="value" style="color: #34C759;">● Online</div>
        </div>
    </div>
    
    <div class="tabs">
        <div class="tab active" onclick="showTab('blocks')">📦 Blocks</div>
        <div class="tab" onclick="showTab('transactions')">💸 Transactions</div>
        <div class="tab" onclick="showTab('contracts')">🧠 Smart Contracts</div>
    </div>
    
    <div class="content" id="content">
        <div class="loading">Loading...</div>
    </div>
</div>

<script>
const NODE_URL = 'http://127.0.0.1:6002';
const DVM_URL = 'http://127.0.0.1:6005';
let currentTab = 'blocks';

async function loadStats() {    try {
        const blocksRes = await fetch(NODE_URL + '/blocks');
        const blocks = await blocksRes.json();
        document.getElementById('total-blocks').textContent = blocks.length;
        
        let totalTxs = 0;
        blocks.forEach(b => { if (b.transactions) totalTxs += b.transactions.length; });
        document.getElementById('total-txs').textContent = totalTxs;
        
        const contractsRes = await fetch(DVM_URL + '/contracts');
        const contracts = await contractsRes.json();
        document.getElementById('total-contracts').textContent = contracts.total;
    } catch (e) {
        console.error(e);
    }
}

async function loadBlocks() {
    try {
        const res = await fetch(NODE_URL + '/blocks');
        const blocks = await res.json();
        
        let html = '<h2 style="color: #F7931A; margin-bottom: 15px;">Latest Blocks</h2>';
        
        blocks.slice().reverse().slice(0, 20).forEach(block => {
            html += '<div class="block-item">';
            html += '<div class="block-header">';
            html += '<div class="block-number">Block #' + block.index + '</div>';
            html += '<div class="label">' + new Date(block.timestamp * 1000).toLocaleString() + '</div>';
            html += '</div>';
            html += '<div class="block-hash">Hash: ' + block.hash + '</div>';
            html += '<div style="margin-top: 10px;">';
            html += '<span class="label">Transactions: </span>';
            html += '<span class="value-highlight">' + (block.transactions ? block.transactions.length : 0) + '</span>';
            html += ' | <span class="label">Nonce: </span>';
            html += '<span class="value-highlight">' + block.nonce + '</span>';
            html += '</div>';
            html += '</div>';
        });
        
        document.getElementById('content').innerHTML = html;
    } catch (e) {
        document.getElementById('content').innerHTML = '<div class="error">Error loading blocks</div>';
    }
}

async function loadTransactions() {
    try {
        const res = await fetch(NODE_URL + '/blocks');
        const blocks = await res.json();        
        let html = '<h2 style="color: #F7931A; margin-bottom: 15px;">Recent Transactions</h2>';
        let txs = [];
        
        blocks.forEach(block => {
            if (block.transactions) {
                block.transactions.forEach(tx => {
                    txs.push({ ...tx, block: block.index, timestamp: block.timestamp });
                });
            }
        });
        
        txs.slice().reverse().slice(0, 30).forEach(tx => {
            html += '<div class="tx-item">';
            html += '<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">';
            html += '<span class="label">Block #' + tx.block + '</span>';
            html += '<span class="label">' + new Date(tx.timestamp * 1000).toLocaleString() + '</span>';
            html += '</div>';
            html += '<div style="margin-bottom: 5px;"><span class="label">From: </span><span style="color: #34C759;">' + (tx.from || 'GENESIS') + '</span></div>';
            html += '<div style="margin-bottom: 5px;"><span class="label">To: </span><span style="color: #FF9500;">' + (tx.to || 'MINER') + '</span></div>';
            html += '<div><span class="label">Amount: </span><span class="value-highlight">' + tx.amount + ' DYX</span></div>';
            html += '</div>';
        });
        
        document.getElementById('content').innerHTML = html;
    } catch (e) {
        document.getElementById('content').innerHTML = '<div class="error">Error loading transactions</div>';
    }
}

async function loadContracts() {
    try {
        const res = await fetch(DVM_URL + '/contracts');
        const data = await res.json();
        
        let html = '<h2 style="color: #F7931A; margin-bottom: 15px;">Smart Contracts</h2>';
        
        if (data.contracts.length === 0) {
            html += '<div class="loading">No contracts deployed yet</div>';
        } else {
            data.contracts.forEach(contract => {
                html += '<div class="contract-item">';
                html += '<div style="margin-bottom: 8px;"><span class="label">Contract ID: </span><span class="value-highlight">' + contract.id + '</span></div>';
                html += '<div style="margin-bottom: 8px;"><span class="label">Creator: </span><span style="color: #34C759;">' + contract.creator + '</span></div>';
                html += '<div><span class="label">Deployed: </span><span>' + new Date(contract.timestamp * 1000).toLocaleString() + '</span></div>';
                html += '</div>';
            });
        }
        
        document.getElementById('content').innerHTML = html;    } catch (e) {
        document.getElementById('content').innerHTML = '<div class="error">Error loading contracts</div>';
    }
}

function showTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    
    if (tab === 'blocks') loadBlocks();
    else if (tab === 'transactions') loadTransactions();
    else if (tab === 'contracts') loadContracts();
}

async function search() {
    const query = document.getElementById('search').value.trim();
    if (!query) return;
    
    // Check if it's a block number
    if (/^\\d+$/.test(query)) {
        showTab('blocks');
        return;
    }
    
    // Check if it's an address
    if (query.startsWith('DX')) {
        try {
            const res = await fetch(NODE_URL + '/balance/' + query);
            const data = await res.json();
            alert('Balance: ' + data.balance + ' DYX');
        } catch (e) {
            alert('Address not found');
        }
        return;
    }
    
    alert('Search not implemented for this query type');
}

// Load initial data
loadStats();
loadBlocks();

// Auto-refresh every 10 seconds
setInterval(() => {
    loadStats();
    if (currentTab === 'blocks') loadBlocks();
    else if (currentTab === 'transactions') loadTransactions();
    else if (currentTab === 'contracts') loadContracts();}, 10000);
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/stats")
def stats():
    try:
        blocks_res = requests.get(NODE_URL + "/blocks", timeout=3)
        blocks = blocks_res.json()
        
        contracts_res = requests.get(DVM_URL + "/contracts", timeout=3)
        contracts = contracts_res.json()
        
        total_txs = sum(len(b.get("transactions", [])) for b in blocks)
        
        return jsonify({
            "total_blocks": len(blocks),
            "total_transactions": total_txs,
            "total_contracts": contracts.get("total", 0),
            "status": "online"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("=" * 50)
    print("DYNAX Block Explorer v1.0")
    print("=" * 50)
    print("Open in browser: http://127.0.0.1:6006")
    print("=" * 50)
    app.run(host="0.0.0.0", port=6006, debug=False)
'''

with open('dynax_explorer.py', 'w') as f:
    f.write(code)

print('✅ สร้าง dynax_explorer.py สำเร็จ!')
