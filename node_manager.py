import os
import time
import subprocess

PORTS = [6001, 6002, 6003]

BASE_CMD = "python3 ~/qchain-website/dynax_p2p_node.py"

def clean_ports():
    print("[CLEAN] killing dynax nodes only")
    os.system("pkill -f dynax")

def start_node(port):
    return subprocess.Popen(
        f"PORT={port} python3 ~/qchain-website/dynax_p2p_node.py",
        shell=True
    )



def main():
    print("=== AUTO RECOVERY NODE SYSTEM STARTED ===")

    print("[1] cleaning ports")
    clean_ports()

    print("[2] starting nodes")

    processes = {}

    for p in PORTS:
        print(f"[START] node {p}")
        processes[p] = start_node(p)
        time.sleep(1)

    print("[3] entering monitor loop")

    while True:
        print("[HEARTBEAT] manager alive")

        time.sleep(5)

if __name__ == "__main__":
    main()
