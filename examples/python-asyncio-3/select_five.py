"""One thread, five sockets, one selector: the OS says which socket is ready."""

import selectors
import socket
import time

from sellers_net import running_sellers

with running_sellers() as ports, selectors.DefaultSelector() as sel:
    print(f"selector: {type(sel).__name__}")
    start = time.monotonic()
    for name, port in ports.items():
        sock = socket.create_connection(("127.0.0.1", port))  # quick on localhost
        sock.sendall(b"kettle-1l\n")
        sock.setblocking(False)
        sel.register(sock, selectors.EVENT_READ, data=name)  # "tell me when it can be read"

    calls = 0
    while sel.get_map():  # until every socket is unregistered
        events = sel.select(timeout=None)  # the thread sleeps here until a socket is ready
        calls += 1
        for key, _mask in events:
            line = key.fileobj.recv(100).decode().strip()
            sel.unregister(key.fileobj)  # unregister first, then close
            key.fileobj.close()
            ms = round((time.monotonic() - start) * 100) * 10
            print(f"{ms:5} ms  ready: {key.data:<8}  read: {line}")
    print(f"select() calls: {calls}")
