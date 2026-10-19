"""A token bucket: at most `rate` calls per second on average, and at most `burst` at once."""

import asyncio


class TokenBucket:
    def __init__(self, rate, burst):
        self.rate, self.burst = rate, burst
        self.tokens = float(burst)  # start full: a burst is allowed straight away
        self.updated = None

    def try_take(self):
        """Take one token if there is one. Never waits: the caller decides what to do without it."""
        now = asyncio.get_running_loop().time()
        if self.updated is not None:  # refill for the time since the last call, up to burst
            self.tokens = min(self.burst, self.tokens + (now - self.updated) * self.rate)
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
