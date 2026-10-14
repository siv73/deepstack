"""A non-blocking socket never makes the thread wait: it says "would block" instead."""

import errno
import socket
import time

from sellers_net import running_sellers

with running_sellers() as ports:
    sock = socket.socket()
    sock.setblocking(False)  # same as sock.settimeout(0.0)
    try:
        sock.connect(("127.0.0.1", ports["seller-a"]))
    except BlockingIOError as e:
        print(f"connect(): BlockingIOError, errno {errno.errorcode[e.errno]} (still connecting)")
    time.sleep(0.01)  # give the connection 10 ms to finish (a selector would tell us exactly when)
    sock.send(b"kettle-1l\n")
    try:
        sock.recv(100)
    except BlockingIOError as e:
        print(f"recv() at once: BlockingIOError, errno {errno.errorcode[e.errno]} (no data yet)")

    start, cpu_start, failed = time.monotonic(), time.process_time(), 0
    while True:  # ask again and again: "busy waiting"
        try:
            line = sock.recv(100)
            break
        except BlockingIOError:
            failed += 1
    wall, cpu = time.monotonic() - start, time.process_time() - cpu_start
    sock.close()
    print(f"answer after about {round(wall * 100) * 10} ms: {line.decode().strip()}")
    print("recv() calls that would have blocked: " + ("over 1,000" if failed > 1_000 else str(failed)))
    print("CPU busy during the wait: " + ("over 50%" if cpu / wall > 0.5 else f"{cpu / wall:.0%}"))
