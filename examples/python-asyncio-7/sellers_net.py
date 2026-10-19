"""The five sellers as real local servers: one plain TCP server per seller on 127.0.0.1.

Wire format, one line each way: the gateway sends "kettle-1l\\n"; the seller waits its
latency and answers "seller-b 1199\\n" (or "ERROR\\n" in fault mode), then closes.
These servers are ordinary blocking code in background threads: they are the test
harness, not the thing being taught.
"""

import socket
import threading
import time
from contextlib import contextmanager, suppress

from sellers import SELLERS


def _answer(conn, seller, fail, garble=False):
    with conn:
        request = b""
        while not request.endswith(b"\n"):
            chunk = conn.recv(100)
            if not chunk:
                return  # the gateway gave up before sending a full line
            request += chunk
        time.sleep(seller.latency_ms / 1000)  # the seller's thinking time
        reply = "ERROR\n" if fail else f"{seller.name} {seller.price}\n"
        if garble:  # a bug on the seller's side: a price that is not a number
            reply = f"{seller.name} 12x9\n"
        with suppress(OSError):  # the gateway may have stopped waiting and closed its end
            conn.sendall(reply.encode())


def _serve(listener, seller, fail, garble=False):
    while True:
        try:
            conn, _ = listener.accept()
        except OSError:
            return  # listener closed: stop serving
        threading.Thread(target=_answer, args=(conn, seller, fail, garble), daemon=True).start()


@contextmanager
def running_sellers(faulty=(), garbled=()):
    """Start the five sellers; yield {name: port}; stop them afterwards.

    `faulty` sellers answer ERROR; `garbled` sellers answer a price that is not a number.
    """
    listeners, ports = [], {}
    for seller in SELLERS:
        listener = socket.create_server(("127.0.0.1", 0))  # port 0: the OS picks a free port
        listeners.append(listener)
        ports[seller.name] = listener.getsockname()[1]
        args = (listener, seller, seller.name in faulty, seller.name in garbled)
        threading.Thread(target=_serve, args=args, daemon=True).start()
    try:
        yield ports
    finally:
        for listener in listeners:
            with suppress(OSError):  # some systems refuse shutdown() on a listening socket
                listener.shutdown(socket.SHUT_RDWR)  # wakes a thread blocked in accept() on Linux
            listener.close()
