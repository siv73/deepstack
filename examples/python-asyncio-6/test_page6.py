"""Part 6: the page shows what the code does, and every check's answer holds."""

import asyncio
import json
from pathlib import Path

from audit import AuditStore
from audit_queue import AuditQueue
from limits import SellerLimits, Skipped
from ratelimit import TokenBucket
from spawn import spawn

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-6"
BODY = (CONTENT / "body.html").read_text()


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_six_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == [f"python-asyncio-{n}" for n in (1, 2, 3, 4, 5)]
    for n in (1, 2, 3, 4, 5):
        other = json.loads((CONTENT.parent / f"python-asyncio-{n}" / "meta.json").read_text())["related"]
        assert other[5].get("slug") == "python-asyncio-6"
    page5 = (CONTENT.parent / "python-asyncio-5" / "body.html").read_text()
    assert '<a href="../python-asyncio-6/index.html">Part 6' in page5
    assert "Next: Part 7" in BODY and "python-asyncio-7/index.html" not in BODY  # page 7 does not exist yet


def test_every_example_program_with_output_is_on_the_page():
    for out in (HERE / "out").glob("*.txt"):
        if f'data-file="{out.stem}.py"' in BODY:
            assert f'data-file="out/{out.stem}.txt"' in BODY, out.stem


def test_sellers_are_still_the_series_numbers():
    from sellers import BUDGET_MS, SELLERS

    assert [(s.name, s.latency_ms, s.price) for s in SELLERS] == [
        ("seller-a", 80, 1249),
        ("seller-b", 120, 1199),
        ("seller-c", 150, 1229),
        ("seller-d", 200, 1215),
        ("seller-e", 900, 1149),
    ]
    assert BUDGET_MS == 250


# ---- rung 1 ------------------------------------------------------------------------


def test_predict_2400_arrivals_for_5_minutes():
    import work_in_work_out as w

    waiting = (2_400 - w.CAPACITY) * 300
    assert waiting == 120_000
    assert round(w.mb(waiting), -1) == 820
    assert waiting / w.CAPACITY == 60


def test_solved_examples_numbers():
    import work_in_work_out as w

    assert round(w.mb(60_000)) == 410
    assert w.CAPACITY * w.IN_GATEWAY_S == 560
    assert 300 * 1024 / 7 / 60 > 700  # prompt 1: 300 MB a minute is about 700 requests a second


# ---- rung 2 ------------------------------------------------------------------------


def test_quiz_maxsize_zero_accepts_everything():
    async def main():
        q = asyncio.Queue(maxsize=0)
        for n in range(50_000):
            q.put_nowait(n)
        return q.qsize(), q.full()

    assert asyncio.run(main()) == (50_000, False)


def test_order_putters_are_woken_first_in_first_out():
    async def main():
        q = asyncio.Queue(maxsize=1)
        q.put_nowait("row-0")
        first = asyncio.create_task(q.put("row-1"))
        await asyncio.sleep(0)
        second = asyncio.create_task(q.put("row-2"))
        await asyncio.sleep(0)
        await q.get()
        await asyncio.sleep(0)
        return first.done(), second.done(), q.get_nowait()

    assert asyncio.run(main()) == (True, False, "row-1")


def test_predict_five_writers_twenty_rows():
    async def main():
        loop = asyncio.get_running_loop()
        start = loop.time()
        q = asyncio.Queue()
        for n in range(20):
            q.put_nowait(n)
        empty_at = None

        async def writer():
            nonlocal empty_at
            while True:
                await q.get()
                if q.empty() and empty_at is None:
                    empty_at = loop.time() - start
                try:
                    await asyncio.sleep(0.02)
                finally:
                    q.task_done()

        pool = [asyncio.create_task(writer()) for _ in range(5)]
        await q.join()
        took = loop.time() - start
        for t in pool:
            t.cancel()
        await asyncio.wait(pool)
        return round(took * 100) * 10, round(empty_at * 100) * 10

    took, empty = asyncio.run(main())
    assert 70 <= took <= 100 and 50 <= empty <= 70


def test_quiz_shutdown_keeps_queued_items_and_refuses_puts():
    async def main():
        q = asyncio.Queue()
        for n in range(4):
            q.put_nowait(n)
        q.shutdown()
        try:
            await q.put("x")
        except asyncio.QueueShutDown:
            refused = True
        taken = [await q.get() for _ in range(4)]
        try:
            await q.get()
        except asyncio.QueueShutDown:
            return refused, taken, "then QueueShutDown"

    assert asyncio.run(main()) == (True, [0, 1, 2, 3], "then QueueShutDown")


def test_quiz_equal_priorities_compare_the_dicts():
    async def main():
        q = asyncio.PriorityQueue()
        q.put_nowait((1, {"shopper": "a"}))
        try:
            q.put_nowait((1, {"shopper": "b"}))
        except TypeError:
            return "TypeError"

    assert asyncio.run(main()) == "TypeError"


# ---- rung 3 ------------------------------------------------------------------------


def test_quiz_locked_is_true_with_a_free_slot_while_waiters_are_in_line():
    async def main():
        sem = asyncio.Semaphore(0)
        waiters = [asyncio.create_task(sem.acquire()) for _ in range(2)]
        await asyncio.sleep(0)
        sem._value = 1  # a free slot while two waiters are in line; inspected only in this test
        locked = sem.locked()
        for w in waiters:
            w.cancel()
        await asyncio.wait(waiters)
        return locked

    assert asyncio.run(main()) is True


def test_predict_an_idle_bucket_still_allows_only_the_burst():
    async def main():
        bucket = TokenBucket(rate=20, burst=5)
        bucket.try_take()
        await asyncio.sleep(0.3)  # idle long enough to refill fully
        bucket.tokens = 5.0
        await asyncio.sleep(0)
        return sum(bucket.try_take() for _ in range(30))

    assert asyncio.run(main()) == 5


def test_predict_a_longer_line_for_seller_c_answers_no_more_requests():
    async def main(line):
        loop = asyncio.get_running_loop()
        start = loop.time()
        limits = SellerLimits({"seller-c": 3}, {"seller-c": line}, {})
        result = {"answered": 0, "cut": 0, "skipped": 0}

        async def call():
            await asyncio.sleep(0.15)

        async def request():
            try:
                async with asyncio.timeout_at(start + 0.25):
                    await limits.call("seller-c", call)
                result["answered"] += 1
            except TimeoutError:
                result["cut"] += 1
            except Skipped:
                result["skipped"] += 1

        async with asyncio.TaskGroup() as tg:
            for _ in range(10):
                tg.create_task(request())
        return result

    assert asyncio.run(main(2)) == {"answered": 3, "cut": 2, "skipped": 5}
    assert asyncio.run(main(7)) == {"answered": 3, "cut": 7, "skipped": 0}


def test_quiz_a_hang_up_during_a_full_audit_queue_keeps_the_row():
    async def main():
        store = AuditStore(ms=40)
        audit = AuditQueue(store, writers=1, maxsize=1)
        audit.start()
        fillers = [spawn(audit.write(f"row-{n}"), name="audit") for n in range(2)]  # one writing, one queued
        await asyncio.sleep(0.005)

        async def handler():
            task = spawn(audit.write("hung-up row"), name="audit")
            await asyncio.shield(task)

        h = asyncio.create_task(handler())
        await asyncio.sleep(0.005)
        h.cancel()  # the shopper hangs up while the row waits for room
        await asyncio.wait([h, *fillers])
        await audit.close()
        return h.cancelled(), store.rows

    cancelled, rows = asyncio.run(main())
    assert cancelled is True
    assert rows == ["row-0", "row-1", "hung-up row"]


def test_a_store_failure_reaches_the_request_waiting_for_its_row():
    class Down(AuditStore):
        async def write(self, row):
            raise ConnectionRefusedError("audit store down")

    async def main():
        audit = AuditQueue(Down(), writers=1)
        audit.start()
        try:
            await audit.write("row")
        except ConnectionRefusedError as exc:
            seen = str(exc)
        await audit.close()
        return seen

    assert asyncio.run(main()) == "audit store down"


# ---- rung 4 ------------------------------------------------------------------------


def test_predict_three_writers_three_bad_rows_join_never_returns():
    async def main():
        q = asyncio.Queue()
        for n in range(30):
            q.put_nowait(n)

        async def writer():
            while True:
                row = await q.get()
                await asyncio.sleep(0.001)
                if row in (4, 9, 17):
                    raise ValueError(row)
                q.task_done()

        pool = [asyncio.create_task(writer()) for _ in range(3)]
        try:
            async with asyncio.timeout(0.3):
                await q.join()
            returned = True
        except TimeoutError:
            returned = False
        alive = sum(not t.done() for t in pool)
        await asyncio.gather(*pool, return_exceptions=True)
        return returned, alive, q.qsize() > 0

    assert asyncio.run(main()) == (False, 0, True)


# ---- rung 5 ------------------------------------------------------------------------


def test_quiz_a_cancelled_request_does_not_stop_its_job_in_a_worker():
    async def main():
        q = asyncio.Queue()
        finished = []

        async def worker():
            while True:
                name, fut = await q.get()
                try:
                    await asyncio.sleep(0.05)  # the seller call, no timeout of its own
                    finished.append(name)
                    if not fut.done():
                        fut.set_result(name)
                finally:
                    q.task_done()

        pool = asyncio.create_task(worker())

        async def request():
            fut = asyncio.get_running_loop().create_future()
            await q.put(("seller-b", fut))
            await fut

        r = asyncio.create_task(request())
        await asyncio.sleep(0.01)
        r.cancel()  # the shopper hangs up
        await asyncio.wait([r])
        await q.join()
        pool.cancel()
        await asyncio.wait([pool])
        return r.cancelled(), finished

    assert asyncio.run(main()) == (True, ["seller-b"])
