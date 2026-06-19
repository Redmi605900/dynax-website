import json
import time
import hashlib
from flask import Flask, jsonify, request

app = Flask(__name__)

class DVM:
    def __init__(self):
        self.contracts = {}
        self.storage = {}
        self.gas_price = 0.001
        self.max_gas = 1000000

    def deploy_contract(self, creator, code, initial_state=None):
        contract_id = hashlib.sha256((str(time.time()) + creator + code).encode()).hexdigest()[:20]
        contract = {
            "id": contract_id,
            "creator": creator,
            "code": code,
            "state": initial_state or {},
            "timestamp": int(time.time()),
            "gas_used": 0
        }
        self.contracts[contract_id] = contract
        self.storage[contract_id] = initial_state or {}
        print("Contract deployed: " + contract_id)
        return contract

    def execute_contract(self, contract_id, function_name, params, caller, gas_limit=100000):
        if contract_id not in self.contracts:
            return {"error": "Contract not found"}

        contract = self.contracts[contract_id]
        state = self.storage[contract_id]
        gas_used = 0

        try:
            exec_env = {
                "state": state,
                "params": params,
                "caller": caller,
                "contract_id": contract_id,
                "gas_used": 0,
                "gas_limit": gas_limit,
                "emit": lambda event, data: print("Event: " + event + " " + str(data))
            }

            exec(contract["code"], exec_env)
            if function_name in exec_env:
                result = exec_env[function_name](params)
            else:
                return {"error": "Function not found: " + function_name}

            gas_used = exec_env.get("gas_used", 100)
            gas_cost = gas_used * self.gas_price

            self.storage[contract_id] = state
            contract["gas_used"] += gas_used

            return {
                "result": result,
                "state": state,
                "gas_used": gas_used,
                "gas_cost": gas_cost
            }

        except Exception as e:
            return {"error": str(e), "gas_used": gas_used}

    def get_contract(self, contract_id):
        if contract_id not in self.contracts:
            return None
        contract = self.contracts[contract_id].copy()
        contract["state"] = self.storage.get(contract_id, {})
        return contract

    def list_contracts(self):
        return [{"id": cid, "creator": c["creator"], "timestamp": c["timestamp"]} for cid, c in self.contracts.items()]

dvm = DVM()

@app.route("/")
def home():
    return jsonify({
        "network": "DYNAX DVM v1.0",
        "status": "running",
        "type": "Layer 1 Smart Contract Platform",
        "endpoints": ["/deploy", "/execute", "/contract/<id>", "/contracts", "/storage/<id>"]
    })

@app.route("/deploy", methods=["POST"])
def deploy():
    data = request.json
    creator = data.get("creator", "anonymous")
    code = data.get("code", "")
    initial_state = data.get("state", {})
    if not code:
        return jsonify({"error": "Code is required"}), 400

    contract = dvm.deploy_contract(creator, code, initial_state)
    return jsonify({"message": "Contract deployed", "contract": contract}), 201

@app.route("/execute", methods=["POST"])
def execute():
    data = request.json
    contract_id = data.get("contract_id")
    function_name = data.get("function")
    params = data.get("params", {})
    caller = data.get("caller", "anonymous")
    gas_limit = data.get("gas_limit", 100000)

    if not contract_id or not function_name:
        return jsonify({"error": "contract_id and function are required"}), 400

    result = dvm.execute_contract(contract_id, function_name, params, caller, gas_limit)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)

@app.route("/contract/<contract_id>")
def get_contract(contract_id):
    contract = dvm.get_contract(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    return jsonify(contract)

@app.route("/contracts")
def list_contracts():
    return jsonify({"contracts": dvm.list_contracts(), "total": len(dvm.contracts)})

@app.route("/storage/<contract_id>")
def get_storage(contract_id):
    if contract_id not in dvm.storage:
        return jsonify({"error": "Contract not found"}), 404
    return jsonify({"contract_id": contract_id, "storage": dvm.storage[contract_id]})

if __name__ == "__main__":
    print("=" * 50)
    print("DYNAX DVM v1.0 - Smart Contract Platform")
    print("=" * 50)
    app.run(host="0.0.0.0", port=6005, debug=False)
