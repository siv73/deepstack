"""Per-seller outcome counts, sent in batches to a metrics service (a local stub).

record() is a coroutine because a full batch is sent before it returns, which waits on
the network. A background task also sends whatever has piled up, every few seconds.
"""

import asyncio
from collections import Counter


class MetricsSink:
    """Stands in for a metrics service. It keeps every batch it receives."""

    def __init__(self, down=False):
        self.down = down
        self.batches = []

    async def send(self, counts):
        await asyncio.sleep(0.005)  # the network round trip
        if self.down:
            raise ConnectionRefusedError("metrics service refused the connection")
        self.batches.append(dict(counts))

    def totals(self):
        total = Counter()
        for batch in self.batches:
            total.update(batch)
        return dict(sorted(total.items()))


class MetricsClient:
    def __init__(self, sink, batch_size=100):
        self.sink, self.batch_size = sink, batch_size
        self.counts, self.pending = Counter(), 0

    async def record(self, seller, outcome):
        self.counts[f"{seller} {outcome}"] += 1
        self.pending += 1
        if self.pending >= self.batch_size:  # a full batch goes out now
            await self.flush()

    async def flush(self):
        if self.pending:
            counts, self.counts, self.pending = self.counts, Counter(), 0
            await self.sink.send(counts)


def outcome(answer, name):
    """'answered', 'timed out' or 'failed' for one seller in a gateway answer."""
    if name in answer.timed_out:
        return "timed out"
    if name in [n for n, _ in answer.failed]:
        return "failed"
    return "answered"
