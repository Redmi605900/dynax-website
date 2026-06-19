import requests
import time
import random

NODE = "http://127.0.0.1:6001"

WALLETS = ["A", "B", "C", "N1", "N2"]

def send():
    sender = random.choice(WALLETS)
    receiver = random.choice(WALLETS)
    amount = random.randint(1, 10)

    if sender == receiver:
        return

    url = f"{NODE}/send/{sender}/{receiver}/{amount}"
    print(requests.get(url).json())

def mine():
    miner = random.choice(WALLETS)
    url = f"{NODE}/mine/{miner}"
    print("MINE:", requests.get(url).json())

if __name__ == "__main__":
    while True:
        action = random.choice(["send", "mine"])

        if action == "send":
            send()
        else:
            mine()

        time.sleep(2)
