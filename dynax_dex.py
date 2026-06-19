import json
import time
import hashlib
from flask import Flask, jsonify, request

app = Flask(__name__)

class DEX:
    def __init__(self):
        self.buy_orders = []
        self.sell_orders = []
        self.trades = []
        self.dyx_balances = {}
        self.usdt_balances = {}

    def get_dyx_balance(self, trader):
        return self.dyx_balances.get(trader, 0)

    def get_usdt_balance(self, trader):
        return self.usdt_balances.get(trader, 0)

    def set_dyx_balance(self, trader, amount):
        self.dyx_balances[trader] = amount

    def set_usdt_balance(self, trader, amount):
        self.usdt_balances[trader] = amount

    def add_order(self, order_type, price, amount, trader):
        if order_type == "sell":
            dyx_balance = self.get_dyx_balance(trader)
            if dyx_balance < amount:
                return {"error": "Insufficient DYX balance: " + str(dyx_balance) + " < " + str(amount)}
            self.dyx_balances[trader] = dyx_balance - amount
        elif order_type == "buy":
            usdt_needed = amount * price
            usdt_balance = self.get_usdt_balance(trader)
            if usdt_balance < usdt_needed:
                return {"error": "Insufficient USDT balance: " + str(usdt_balance) + " < " + str(usdt_needed)}
            self.usdt_balances[trader] = usdt_balance - usdt_needed

        order = {
            "id": hashlib.sha256((str(time.time()) + trader + str(amount)).encode()).hexdigest()[:16],
            "type": order_type,
            "price": price,
            "amount": amount,
            "trader": trader,
            "timestamp": int(time.time()),
            "status": "open"
        }
        if order_type == "buy":
            self.buy_orders.append(order)
            self.buy_orders.sort(key=lambda x: x["price"], reverse=True)
        else:
            self.sell_orders.append(order)
            self.sell_orders.sort(key=lambda x: x["price"])

        self.match_orders()
        return order

    def match_orders(self):
        while self.buy_orders and self.sell_orders:
            best_buy = self.buy_orders[0]
            best_sell = self.sell_orders[0]

            if best_buy["price"] >= best_sell["price"]:
                trade_amount = min(best_buy["amount"], best_sell["amount"])
                trade_price = (best_buy["price"] + best_sell["price"]) / 2
                total_usdt = trade_amount * trade_price

                self.dyx_balances[best_buy["trader"]] = self.dyx_balances.get(best_buy["trader"], 0) + trade_amount
                self.usdt_balances[best_sell["trader"]] = self.usdt_balances.get(best_sell["trader"], 0) + total_usdt

                trade = {
                    "buyer": best_buy["trader"],
                    "seller": best_sell["trader"],
                    "amount": trade_amount,
                    "price": trade_price,
                    "timestamp": int(time.time())
                }
                self.trades.append(trade)
                print("Trade: " + str(trade_amount) + " DYX @ " + str(trade_price) + " USDT")

                best_buy["amount"] -= trade_amount
                best_sell["amount"] -= trade_amount

                if best_buy["amount"] == 0:
                    self.buy_orders.pop(0)
                if best_sell["amount"] == 0:
                    self.sell_orders.pop(0)
            else:
                break

    def get_order_book(self):
        return {
            "buy_orders": self.buy_orders[:10],
            "sell_orders": self.sell_orders[:10],
            "spread": self.get_spread(),
            "last_price": self.get_last_price()        }

    def get_spread(self):
        if self.buy_orders and self.sell_orders:
            return self.buy_orders[0]["price"] - self.sell_orders[0]["price"]
        return 0

    def get_last_price(self):
        if self.trades:
            return self.trades[-1]["price"]
        return 0

dex = DEX()

@app.route("/")
def home():
    return jsonify({
        "network": "DYNAX DEX v2.0",
        "status": "running",
        "type": "Layer 1 Native DEX",
        "endpoints": ["/order", "/orderbook", "/trades", "/price", "/balance/<trader>"]
    })

@app.route("/balance/<trader>")
def get_balance(trader):
    return jsonify({
        "trader": trader,
        "dyx": dex.get_dyx_balance(trader),
        "usdt": dex.get_usdt_balance(trader)
    })

@app.route("/set_balance", methods=["POST"])
def set_balance():
    data = request.json
    trader = data.get("trader")
    dyx = data.get("dyx", 0)
    usdt = data.get("usdt", 0)
    dex.set_dyx_balance(trader, dyx)
    dex.set_usdt_balance(trader, usdt)
    return jsonify({"message": "Balance set", "dyx": dyx, "usdt": usdt})

@app.route("/order", methods=["POST"])
def place_order():
    data = request.json
    order_type = data.get("type")
    price = float(data.get("price", 0))
    amount = float(data.get("amount", 0))
    trader = data.get("trader", "anonymous")

    if order_type not in ["buy", "sell"]:        return jsonify({"error": "Invalid order type"}), 400

    if price <= 0 or amount <= 0:
        return jsonify({"error": "Price and amount must be positive"}), 400

    result = dex.add_order(order_type, price, amount, trader)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"message": "Order placed", "order": result}), 201

@app.route("/orderbook")
def get_orderbook():
    return jsonify(dex.get_order_book())

@app.route("/trades")
def get_trades():
    return jsonify({"trades": dex.trades[-20:], "total": len(dex.trades)})

@app.route("/price")
def get_price():
    return jsonify({
        "last_price": dex.get_last_price(),
        "spread": dex.get_spread(),
        "volume_24h": sum(t["amount"] for t in dex.trades[-100:])
    })

if __name__ == "__main__":
    print("=" * 50)
    print("DYNAX DEX v2.0 - Layer 1 Native DEX")
    print("=" * 50)
    app.run(host="0.0.0.0", port=6004, debug=False)
