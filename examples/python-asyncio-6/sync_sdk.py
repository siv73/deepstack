"""seller-e's only client library: a sync SDK built on blocking sockets.

It never awaits anything. Whoever calls get_price() is held for the whole call, which is
seller-e's 900 ms. Like the seller servers, this stands in for a real vendor library.
"""

import socket
import threading
import time

from sellers import Offer, SellerError


class SyncSellerClient:
    def __init__(self, port, timeout=5.0):
        self.port, self.timeout = port, timeout
        self.started = 0  # calls that actually began running
        self.running = 0  # calls running right now, in any thread
        self.peak = 0  # the most calls running at once
        self.last_finished = None  # time.monotonic() when the last call ended, however it ended
        self._lock = threading.Lock()

    def get_price(self, item, timeout=None):
        """Ask seller-e. `timeout` (seconds) overrides the client's own socket timeout for this call."""
        with self._lock:
            self.started += 1
            self.running += 1
            self.peak = max(self.peak, self.running)
        try:
            limit = self.timeout if timeout is None else timeout
            with socket.create_connection(("127.0.0.1", self.port), timeout=limit) as sock:
                sock.sendall(f"{item}\n".encode())
                line = sock.makefile().readline().strip()  # this thread waits here for the answer
        finally:
            with self._lock:
                self.running -= 1
                self.last_finished = time.monotonic()
        if line == "ERROR":
            raise SellerError("seller-e failed")
        name, price = line.split()
        return Offer(name, int(price))
