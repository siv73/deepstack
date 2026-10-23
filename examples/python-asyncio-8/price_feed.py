"""seller-e's SDK can also push price changes. It calls your callback on its own thread.

Like sync_sdk.py, this stands in for a vendor library: plain threads, no asyncio.
"""

import threading
import time

from sellers import Offer


class PriceFeed:
    def __init__(self, changes):
        self.changes = changes  # [(seconds after subscribe, item, new price)]
        self.acks = []  # what each callback returned: the vendor waits for it
        self.thread = None

    def subscribe(self, callback):
        """Start the SDK's own thread; it calls callback(item, offer) for each change, in order."""

        def run():
            started = time.monotonic()
            for at, item, price in self.changes:
                time.sleep(max(0.0, started + at - time.monotonic()))
                self.acks.append(callback(item, Offer("seller-e", price)))  # blocks this thread only

        self.thread = threading.Thread(target=run, name="seller-e-feed", daemon=True)
        self.thread.start()

    def join(self, timeout=None):
        self.thread.join(timeout)
