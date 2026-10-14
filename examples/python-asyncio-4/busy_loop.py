"""Two ways to wait 900 ms for seller-e: spinning on recv() vs sleeping in select()."""

import selectors
import socket
import time

from sellers_net import running_sellers


def connect(port):
    sock = socket.create_connection(("127.0.0.1", port))
    sock.sendall(b"kettle-1l\n")
    sock.setblocking(False)
    return sock


def spin(sock):  # busy loop: ask again and again
    while True:
        try:
            return sock.recv(100)
        except BlockingIOError:
            pass


def wait_with_selector(sock):  # ask the OS to wake us when there is data
    with selectors.DefaultSelector() as sel:
        sel.register(sock, selectors.EVENT_READ)
        sel.select()
        sel.unregister(sock)
    return sock.recv(100)


with running_sellers() as ports:
    for label, wait in (("spinning", spin), ("selector", wait_with_selector)):
        sock = connect(ports["seller-e"])
        start, cpu_start = time.monotonic(), time.process_time()
        wait(sock)
        sock.close()
        wall, cpu = time.monotonic() - start, time.process_time() - cpu_start
        share = "over 50%" if cpu / wall > 0.5 else "under 5%" if cpu / wall < 0.05 else f"{cpu / wall:.0%}"
        print(f"{label}: waited about {round(wall * 10) * 100} ms; CPU busy {share} of that time")
