"""Prices per (seller, item), each kept for `ttl` seconds on the loop's clock."""

import asyncio


class PriceCache:
    def __init__(self, ttl):
        self.ttl = ttl
        self.entries = {}  # (seller, item) -> (offer, expires at)

    def get(self, seller, item):
        """The cached offer if it is still fresh, else None. Never awaits."""
        entry = self.entries.get((seller, item))
        if entry is None or entry[1] <= asyncio.get_running_loop().time():
            return None
        return entry[0]

    def put(self, seller, item, offer):
        self.entries[(seller, item)] = (offer, asyncio.get_running_loop().time() + self.ttl)
