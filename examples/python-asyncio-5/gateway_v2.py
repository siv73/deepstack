"""Gateway v2: Part 1's toy loop, now waiting on real sockets through a selector."""

import errno
import socket

from sellers import BUDGET_MS, Offer, cheapest
from sellers_net import running_sellers
from toyloop_io import IOLoop, readable, writable


async def ask_seller(loop, name, port, item):
    sock = socket.socket()
    sock.setblocking(False)
    try:
        code = sock.connect_ex(("127.0.0.1", port))  # returns at once
        if code not in (0, errno.EINPROGRESS):
            raise OSError(code, errno.errorcode[code])
        await writable(sock)  # connected
        sock.send(f"{item}\n".encode())  # one short line fits the send buffer
        await readable(sock)  # the seller has answered
        line = sock.recv(100).decode()
    finally:
        sock.close()
    seller, price = line.split()
    print(f"{loop.now:5} ms  {seller} answered {int(price):,}")
    return Offer(seller, int(price))


def compare(ports, item, budget_ms=None):
    loop = IOLoop()
    tasks = [loop.spawn(ask_seller(loop, name, port, item), name) for name, port in ports.items()]
    loop.run(until=budget_ms)
    for task in tasks:
        if not task.done:
            loop.cancel(task)
    loop.close()
    offers = [t.result for t in tasks if t.done]
    missed = [t.name for t in tasks if not t.done]
    return cheapest(offers), missed, loop


def report(best, missed, loop):
    line = f"cheapest: {best.seller} at {best.price:,} after {loop.now:,} ms"
    print(line + ("; missed: " + ", ".join(missed) if missed else ""))


if __name__ == "__main__":
    with running_sellers() as ports:
        print("-- wait for every seller --")
        report(*compare(ports, "kettle-1l"))
        print(f"-- stop at the {BUDGET_MS} ms budget --")
        report(*compare(ports, "kettle-1l", budget_ms=BUDGET_MS))
