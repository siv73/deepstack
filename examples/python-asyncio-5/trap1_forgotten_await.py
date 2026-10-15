"""Trap 1: one missing await. The shopper's answer is right; the seller metrics are empty."""

import asyncio
import gc
import warnings

from gateway_v4 import Gateway, report
from metrics import MetricsClient, MetricsSink, outcome
from sellers_net import running_sellers


class ForgotAwait(Gateway):
    def __init__(self, ports, metrics):
        super().__init__(ports)
        self.metrics = metrics

    async def compare(self, item):
        answer = await super().compare(item)
        for name in self.ports:
            self.metrics.record(name, outcome(answer, name))  # BUG: no await
        return answer


class Fixed(ForgotAwait):
    async def compare(self, item):
        answer = await Gateway.compare(self, item)
        for name in self.ports:
            await self.metrics.record(name, outcome(answer, name))
        return answer


async def run(gateway_class, ports):
    sink = MetricsSink()
    metrics = MetricsClient(sink)
    report(await gateway_class(ports, metrics).compare("kettle-1l"))
    await metrics.flush()  # send whatever was recorded
    print("metrics service received:", sink.totals())


async def main():
    with running_sellers() as ports:
        print("-- one await missing --")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await run(ForgotAwait, ports)
            gc.collect()  # the dropped coroutines are cleaned up here
        messages = {str(w.message) for w in caught}
        print(f"RuntimeWarnings: {len(caught)}, all saying: {', '.join(messages)}")
        print("-- the await restored --")
        await run(Fixed, ports)


if __name__ == "__main__":
    asyncio.run(main())
