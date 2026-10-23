"""Part 3: the page shows what the code does, and every check's answer holds."""

import asyncio
import contextlib
import io
import json
from pathlib import Path

import gateway_v4
import pytest
from gateway_v3 import ask_seller
from sellers import BUDGET_MS, SellerError
from sellers_net import running_sellers

HERE = Path(__file__).parent
CONTENT = HERE.parent.parent / "content" / "python-asyncio-3"
BODY = (CONTENT / "body.html").read_text()
ITEM = "kettle-1l"


def quiet(coro):
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(coro)


def ms(loop, start):
    return (loop.time() - start) * 1000


# ---- the series plan and the links ---------------------------------------------


def test_meta_keeps_the_series_plan_and_links_all_three_pages():
    meta = json.loads((CONTENT / "meta.json").read_text())
    plan = json.loads((CONTENT.parent / "python-asyncio-1" / "meta.json").read_text())["related"]
    assert [r["label"] for r in meta["related"]] == [r["label"] for r in plan]
    assert [p["slug"] for p in meta["prereqs"]] == ["python-asyncio-1", "python-asyncio-2"]
    assert plan[2].get("slug") == "python-asyncio-3"
    page2_meta = json.loads((CONTENT.parent / "python-asyncio-2" / "meta.json").read_text())
    assert page2_meta["related"][2].get("slug") == "python-asyncio-3"
    page2 = (CONTENT.parent / "python-asyncio-2" / "body.html").read_text()
    assert '<a href="../python-asyncio-3/index.html">' in page2


def test_every_example_program_with_output_is_on_the_page():
    for out in (HERE / "out").glob("*.txt"):
        if f'data-file="{out.stem}.py"' in BODY:
            assert f'data-file="out/{out.stem}.txt"' in BODY, out.stem


def test_sellers_are_still_the_series_numbers():
    from sellers import SELLERS

    assert [(s.name, s.latency_ms, s.price) for s in SELLERS] == [
        ("seller-a", 80, 1249),
        ("seller-b", 120, 1199),
        ("seller-c", 150, 1229),
        ("seller-d", 200, 1215),
        ("seller-e", 900, 1149),
    ]
    assert BUDGET_MS == 250


# ---- rung 1 and 2 checks -------------------------------------------------------


def test_predict_await_d_then_tasks_a_and_b_takes_about_320ms():
    async def main():
        with running_sellers() as ports:
            loop = asyncio.get_running_loop()
            start = loop.time()
            await ask_seller(start, "seller-d", ports["seller-d"], ITEM)
            ta = asyncio.create_task(ask_seller(start, "seller-a", ports["seller-a"], ITEM))
            tb = asyncio.create_task(ask_seller(start, "seller-b", ports["seller-b"], ITEM))
            await ta
            await tb
            return ms(loop, start)

    assert abs(quiet(main()) - 320) <= 60


def test_quiz_create_task_then_await_coroutine_then_sleep0():
    log = []

    async def log_it(word):
        log.append(word)

    async def main():
        t = asyncio.create_task(log_it("A"))
        await log_it("B")
        await asyncio.sleep(0)
        log.append("C")
        await t

    asyncio.run(main())
    assert log == ["B", "A", "C"]


def test_quiz_gather_raises_at_first_failure_and_leaves_c_running():
    async def main():
        with running_sellers(faulty={"seller-b"}) as ports:
            loop = asyncio.get_running_loop()
            start = loop.time()
            tasks = {n: asyncio.create_task(ask_seller(start, n, p, ITEM)) for n, p in ports.items()}
            with pytest.raises(SellerError):
                await asyncio.gather(*tasks.values())
            raised_at = ms(loop, start)
            await asyncio.sleep(0.01)  # 130 ms
            c_running_at_130 = not tasks["seller-c"].done()
            await asyncio.wait(tasks.values())
            return raised_at, c_running_at_130, tasks["seller-c"].result().price

    raised_at, c_running, c_price = quiet(main())
    assert abs(raised_at - 120) <= 60 and c_running and c_price == 1229


def test_quiz_taskgroup_cancels_d_just_after_b_fails():
    cancelled_at = {}

    async def watched(start, name, port):
        try:
            return await ask_seller(start, name, port, ITEM)
        except asyncio.CancelledError:
            cancelled_at[name] = ms(asyncio.get_running_loop(), start)
            raise

    async def main():
        with running_sellers(faulty={"seller-b"}) as ports:
            start = asyncio.get_running_loop().time()
            with pytest.raises(ExceptionGroup):
                async with asyncio.TaskGroup() as tg:
                    for n, p in ports.items():
                        tg.create_task(watched(start, n, p))

    quiet(main())
    assert set(cancelled_at) == {"seller-c", "seller-d", "seller-e"}
    assert 120 <= cancelled_at["seller-d"] <= 180


def test_quiz_except_star_runs_once_and_unmatched_propagates():
    calls = []

    async def main():
        async def boom(exc):
            await asyncio.sleep(0)
            raise exc

        try:
            async with asyncio.TaskGroup() as tg:
                for exc in (SellerError("c"), TimeoutError(), SellerError("b")):
                    tg.create_task(boom(exc))
        except* SellerError as g:
            calls.append(len(g.exceptions))

    with pytest.raises(ExceptionGroup) as info:
        asyncio.run(main())
    assert calls == [2]
    assert [type(e) for e in info.value.exceptions] == [TimeoutError]


def test_predict_as_completed_with_1220_stops_at_seller_b():
    async def main():
        with running_sellers() as ports:
            loop = asyncio.get_running_loop()
            start = loop.time()
            tasks = [asyncio.create_task(ask_seller(start, n, p, ITEM), name=n) for n, p in ports.items()]
            async for done in asyncio.as_completed(tasks):
                if done.result().price <= 1220:
                    winner, at = done.get_name(), ms(loop, start)
                    break
            running = sorted(t.get_name() for t in tasks if not t.done())
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            return winner, at, running

    winner, at, running = quiet(main())
    assert winner == "seller-b" and abs(at - 120) <= 60
    assert running == ["seller-c", "seller-d", "seller-e"]


def test_quiz_eager_task_that_reaches_readline_is_pending_after_create_task():
    async def main():
        with running_sellers() as ports:
            asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
            start = asyncio.get_running_loop().time()
            task = asyncio.create_task(ask_seller(start, "seller-a", ports["seller-a"], ITEM))
            pending = not task.done()
            await task
            return pending

    assert quiet(main())


# ---- rung 3 checks -------------------------------------------------------------


def test_quiz_cap_of_2_seller_c_answers_at_230ms():
    answered = {}

    async def main():
        with running_sellers() as ports:
            loop = asyncio.get_running_loop()
            start, limit = loop.time(), asyncio.Semaphore(2)

            async def capped(name, port):
                async with limit:
                    await ask_seller(start, name, port, ITEM)
                    answered[name] = ms(loop, start)

            async with asyncio.TaskGroup() as tg:
                for n, p in ports.items():
                    tg.create_task(capped(n, p))

    quiet(main())
    assert abs(answered["seller-c"] - 230) <= 60


def test_semaphore_serves_waiters_first_in_first_out():
    order = []

    async def main():
        limit = asyncio.Semaphore(1)
        await limit.acquire()

        async def waiter(i):
            async with limit:
                order.append(i)

        tasks = [asyncio.create_task(waiter(i)) for i in range(5)]
        await asyncio.sleep(0)
        limit.release()
        await asyncio.gather(*tasks)

    asyncio.run(main())
    assert order == [0, 1, 2, 3, 4]


def test_quiz_nested_timeout_inner_fires_at_100ms_and_request_goes_on():
    async def main():
        loop = asyncio.get_running_loop()
        start = loop.time()
        async with asyncio.timeout_at(start + 0.25):
            try:
                async with asyncio.timeout(0.1):
                    await asyncio.sleep(0.2)  # seller-d's 200 ms
            except TimeoutError:
                inner = ms(loop, start)
            await asyncio.sleep(0.01)
        return inner

    assert abs(asyncio.run(main()) - 100) <= 30


def test_timeout_is_a_deadline_on_the_loop_clock():
    async def main():
        loop = asyncio.get_running_loop()
        cm = asyncio.timeout(0.25)
        return cm.when() - loop.time()

    assert 0.24 <= asyncio.run(main()) <= 0.25


def test_predict_gateway_v4_cap_of_2():
    async def main():
        with running_sellers() as ports:
            return await gateway_v4.Gateway(ports, max_in_flight=2).compare(ITEM)

    answer = quiet(main())
    assert (answer.best.seller, answer.best.price) == ("seller-b", 1199)
    assert answer.timed_out == ["seller-d", "seller-e"] and not answer.failed
    assert abs(answer.ms - 250) <= 60


def test_gateway_v4_leaves_nothing_running_and_shares_its_cap():
    async def main():
        with running_sellers() as ports:
            gw = gateway_v4.Gateway(ports, max_in_flight=4)
            async with asyncio.TaskGroup() as tg:
                requests = [tg.create_task(gw.compare(ITEM)) for _ in range(3)]
            others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            return [r.result() for r in requests], others, gw.limit

    answers, others, limit = quiet(main())
    assert others == []
    assert not limit.locked()  # every slot was given back
    assert all(a.ms <= 310 for a in answers)


# ---- rung 4 and 5 checks -------------------------------------------------------


def test_predict_failure_at_900ms_both_tools_raise_with_nothing_running():
    async def main():
        with running_sellers(faulty={"seller-e"}) as ports:
            loop = asyncio.get_running_loop()
            start = loop.time()
            tasks = [asyncio.create_task(ask_seller(start, n, p, ITEM)) for n, p in ports.items()]
            with pytest.raises(SellerError):
                await asyncio.gather(*tasks)
            gather_at, gather_running = ms(loop, start), [t for t in tasks if not t.done()]
            start = loop.time()
            with pytest.raises(ExceptionGroup):
                async with asyncio.TaskGroup() as tg:
                    group = [tg.create_task(ask_seller(start, n, p, ITEM)) for n, p in ports.items()]
            return gather_at, gather_running, ms(loop, start), [t for t in group if t.cancelled()]

    gather_at, gather_running, group_at, group_cancelled = quiet(main())
    assert abs(gather_at - 900) <= 60 and gather_running == []
    assert abs(group_at - 900) <= 60 and group_cancelled == []


def test_quiz_health_check_first_answer_and_nothing_left_running():
    async def main():
        with running_sellers() as ports:
            loop = asyncio.get_running_loop()
            start = loop.time()
            replicas = ["seller-c", "seller-a", "seller-d"]
            async with asyncio.timeout(1):
                async with asyncio.TaskGroup() as tg:
                    tasks = [tg.create_task(ask_seller(start, n, ports[n], ITEM), name=n) for n in replicas]
                    async for first in asyncio.as_completed(tasks):
                        winner, at = first.get_name(), ms(loop, start)
                        for t in tasks:
                            t.cancel()
                        break
            left = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            return winner, at, left

    winner, at, left = quiet(main())
    assert winner == "seller-a" and abs(at - 80) <= 60 and left == []
