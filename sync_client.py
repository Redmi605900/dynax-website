import requests

PEERS = [
    "http://127.0.0.1:6001",
    "http://127.0.0.1:6002",
    "http://127.0.0.1:6003"
]

def get_chain(peer):
    try:
        return requests.get(peer + "/chain", timeout=3).json()
    except:
        return None

def sync():
    chains = []

    for p in PEERS:
        c = get_chain(p)
        if c:
            chains.append(c)

    if not chains:
        print("No peers available")
        return

    best = max(chains, key=len)

    print("Best chain:", len(best))

    for p in PEERS:
        try:
            r = requests.post(p + "/update_chain", json={"chain": best}, timeout=3)
            print(p, r.json())
        except:
            print(p, "failed")

if __name__ == "__main__":
    sync()
