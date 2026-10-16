"""Gateway v0 on real sockets: one thread, blocking sockets, one seller after another."""

import socket
import time

from sellers import Offer, cheapest
from sellers_net import running_sellers


def ask(port, item):
    with socket.create_connection(("127.0.0.1", port)) as sock:  # blocking by default
        sock.sendall(f"{item}\n".encode())
        line = sock.recv(100).decode()  # the thread stops here until the answer arrives
    name, price = line.split()
    return Offer(name, int(price))


with running_sellers() as ports:
    start, cpu_start = time.monotonic(), time.process_time()
    offers = []
    for name, port in ports.items():
        offers.append(ask(port, "kettle-1l"))
        ms = round((time.monotonic() - start) * 100) * 10  # nearest 10 ms
        print(f"{ms:5} ms  {name} answered {offers[-1].price:,}")
    cpu_ms = (time.process_time() - cpu_start) * 1000
    best = cheapest(offers)
    print(f"cheapest: {best.seller} at {best.price:,} after {ms:,} ms")
    print("CPU time used while waiting: " + ("under 50 ms" if cpu_ms < 50 else f"{cpu_ms:.0f} ms"))
