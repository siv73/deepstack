"""A seller with a fixed number of workers, for overload experiments.

Same wire format as sellers_net.py. Connections wait in a queue until one of the
`workers` threads picks them up; each job takes `latency_ms`. The server counts the jobs
it finished, whether or not anyone was still waiting for the answer. Test harness only.
"""

import queue
import socket
import threading
import time
from contextlib import contextmanager, suppress


class LimitedSeller:
    def __init__(self, name, latency_ms, price, workers):
        self.name, self.latency_ms, self.price, self.workers = name, latency_ms, price, workers
        self.jobs_done = 0
        self.last_done = None  # time.monotonic() when the last job finished
        self._lock = threading.Lock()
        self._queue = queue.Queue()

    def _work(self):
        while (conn := self._queue.get()) is not None:
            with conn:
                with suppress(OSError):
                    conn.recv(100)  # the request line (already sent by the gateway)
                time.sleep(self.latency_ms / 1000)  # the seller does the work either way
                with self._lock:
                    self.jobs_done += 1
                    self.last_done = time.monotonic()
                with suppress(OSError):  # the gateway may have given up and closed
                    conn.sendall(f"{self.name} {self.price}\n".encode())

    def _accept(self, listener):
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            self._queue.put(conn)

    @contextmanager
    def running(self):
        listener = socket.create_server(("127.0.0.1", 0), backlog=1024)
        threads = [threading.Thread(target=self._work, daemon=True) for _ in range(self.workers)]
        threads.append(threading.Thread(target=self._accept, args=(listener,), daemon=True))
        for t in threads:
            t.start()
        try:
            yield listener.getsockname()[1]
        finally:
            with suppress(OSError):
                listener.shutdown(socket.SHUT_RDWR)
            listener.close()
            for _ in range(self.workers):
                self._queue.put(None)
