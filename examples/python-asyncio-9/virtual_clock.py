"""A loop whose clock moves only when every Task is waiting for a timer: tests that never sleep.

Built from two public pieces: SelectorEventLoop accepts the selector it should use, and every
timer in asyncio (sleep, call_later, timeout, timeout_at) reads loop.time(). When the loop has
nothing ready and asks the selector to wait `timeout` seconds for a timer, this selector checks
the real sockets without waiting and, if none is ready, moves the clock forward by `timeout`
instead of sleeping. 900 ms of seller-e takes no real time at all.
"""

import asyncio
import selectors


class VirtualSelector(selectors.DefaultSelector):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop

    def select(self, timeout=None):
        ready = super().select(0)  # real sockets (and the loop's own wake-up pipe): never wait
        if ready:
            return ready
        if timeout is None:  # no timer at all: something outside the clock must wake us
            return super().select(None)
        self.loop.now += timeout  # the next timer is due in `timeout`: jump straight to it
        return []


class VirtualClockLoop(asyncio.SelectorEventLoop):
    """Pass as loop_factory: asyncio.run(main(), loop_factory=VirtualClockLoop)."""

    def __init__(self):
        self.now = 0.0  # seconds since the loop was created, on the virtual clock
        super().__init__(VirtualSelector(self))

    def time(self):
        return self.now

    def advance(self, seconds):
        """Make the current step 'take' `seconds`: a test's stand-in for a blocking call."""
        self.now += seconds
