"""Single-flight: at most one call in flight per key; everyone else who asks for that key shares it.

No lock is needed on one event loop: the lookup and the insert have no await between them,
so no other Task can run in between. The shared call runs as its own owned Task in a fresh
context, so no caller's cancellation, deadline or request id belongs to it.
"""

import contextvars

from spawn import spawn


class SingleFlight:
    def __init__(self):
        self.flights = {}  # key -> the Task doing the one call for that key
        self.started = 0  # calls started: a metric

    def start(self, key, make_call, *, name):
        """Return the Task for `key`, starting `make_call()` only if none is in flight."""
        task = self.flights.get(key)
        if task is None:  # check ...
            self.started += 1
            task = spawn(make_call(), name=name, context=contextvars.Context())
            self.flights[key] = task  # ... and act, with no await in between
            task.add_done_callback(lambda done: self._forget(key, done))
        return task

    def _forget(self, key, done):
        if self.flights.get(key) is done:  # finished: the next caller starts a new call
            del self.flights[key]
