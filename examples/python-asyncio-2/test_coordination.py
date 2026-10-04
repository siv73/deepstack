"""Rung 3-4 behaviours: queues, locks, threads, async generators, eager tasks."""

import asyncio
import sys
import threading

import bridge
import cursor
import eager
import pytest
import stock
import worker_bug

needs_313 = pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown needs Python 3.13+")


class Recorder:
    def __init__(self, delay=0.01, fail_on=None):
        self.delay, self.fail_on = delay, fail_on
        self.done: list[int] = []
        self.in_flight = self.peak = 0

    async def handle(self, item):
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            if item == self.fail_on:
                raise ValueError(item)
            self.done.append(item)
        finally:
            self.in_flight -= 1


@needs_313
def test_pipeline_processes_everything_with_bounded_queue():
    import pipeline

    rec = Recorder()

    async def main():
        await pipeline.run_pipeline(range(200), rec.handle, workers=4, maxsize=10)

    asyncio.run(main())
    assert sorted(rec.done) == list(range(200))
    assert rec.peak == 4


@needs_313
def test_producer_waits_when_queue_is_full():
    import pipeline

    sizes: list[int] = []

    async def handle(item):
        await asyncio.sleep(0.005)

    async def main():
        orig_put = asyncio.Queue.put

        async def spy_put(self, item):
            await orig_put(self, item)
            sizes.append(self.qsize())

        asyncio.Queue.put = spy_put
        try:
            await pipeline.run_pipeline(range(100), handle, workers=2, maxsize=5)
        finally:
            asyncio.Queue.put = orig_put

    asyncio.run(main())
    assert max(sizes) <= 5  # never more than maxsize waiting in memory


@needs_313
def test_pipeline_fails_fast_instead_of_hanging():
    import pipeline

    rec = Recorder(fail_on=7)

    async def main():
        async with asyncio.timeout(2):
            await pipeline.run_pipeline(range(100), rec.handle, workers=3, maxsize=5)

    with pytest.raises(ExceptionGroup) as info:
        asyncio.run(main())
    assert any(isinstance(e, ValueError) for e in info.value.exceptions)


def test_worker_bug_hangs_join_forever():
    rec = Recorder(fail_on=3)

    async def main():
        async with asyncio.timeout(0.5):
            await worker_bug.process_all(range(10), rec.handle, workers=2)

    with pytest.raises(TimeoutError):
        asyncio.run(main())


def test_unbounded_queue_grows_with_the_backlog():
    async def main():
        q: asyncio.Queue = asyncio.Queue()  # maxsize=0: no limit
        for i in range(100_000):
            await q.put(i)  # never waits
        return q.qsize(), q.full()

    assert asyncio.run(main()) == (100_000, False)


def test_racy_check_then_act_oversells():
    async def main():
        s = stock.Stock(1)
        results = await asyncio.gather(*(s.reserve_racy() for _ in range(10)))
        return sum(results), s.units

    assert asyncio.run(main()) == (10, -9)


def test_lock_makes_check_then_act_safe():
    async def main():
        s = stock.Stock(1)
        results = await asyncio.gather(*(s.reserve_safe() for _ in range(10)))
        return sum(results), s.units

    assert asyncio.run(main()) == (1, 0)


def test_thread_hands_work_to_the_loop_in_order():
    seen: list[tuple[int, int]] = []

    async def main():
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()

        async def handle(msg):
            await asyncio.sleep(0.001)
            seen.append((msg, threading.get_ident()))

        t = bridge.consume_in_thread(loop, handle, range(5))
        while t.is_alive():
            await asyncio.sleep(0.01)
        return loop_thread

    loop_thread = asyncio.run(main())
    assert [m for m, _ in seen] == [0, 1, 2, 3, 4]
    assert {tid for _, tid in seen} == {loop_thread}  # handlers ran on the loop's thread


def test_call_soon_threadsafe_delivers_to_the_queue():
    async def main():
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        th = threading.Thread(target=bridge.notify_from_thread, args=(loop, q, "ping"))
        th.start()
        async with asyncio.timeout(1):
            return await q.get()

    assert asyncio.run(main()) == "ping"


def test_leaky_generator_cleans_up_late():
    log: list[str] = []

    async def main():
        await cursor.first_big_leaky(log)
        right_after = list(log)
        await asyncio.sleep(0.05)
        return right_after

    right_after = asyncio.run(main())
    assert right_after == ["cursor opened"]  # cleanup had not run when we returned
    assert log == ["cursor opened", "cursor closed"]  # it ran later, in another task


def test_aclosing_cleans_up_before_returning():
    log: list[str] = []

    async def main():
        await cursor.first_big_safe(log)
        return list(log)

    assert asyncio.run(main()) == ["cursor opened", "cursor closed"]


def test_default_tasks_start_later():
    assert asyncio.run(eager.run(eager=False)) == ["after create_task", "lookup ran"]


def test_eager_tasks_run_inside_create_task():
    assert asyncio.run(eager.run(eager=True)) == ["lookup ran", "after create_task"]
