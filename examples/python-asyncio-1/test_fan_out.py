"""fan_out.fetch_all: cap, order, group failure, deadline."""

import asyncio
import time

import fan_out
import pytest


class FakeHttp:
    def __init__(self, delay: float = 0.05, fail: str | None = None):
        self.delay, self.fail = delay, fail
        self.in_flight = self.peak = 0
        self.cancelled: list[str] = []
        self.completed = 0

    async def fetch(self, url: str) -> bytes:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(0.01 if url == self.fail else self.delay)
            if url == self.fail:
                raise ConnectionError(url)
            self.completed += 1
            return url.encode()
        except asyncio.CancelledError:
            self.cancelled.append(url)
            raise
        finally:
            self.in_flight -= 1


URLS = [f"https://api.example/{i}" for i in range(50)]


def test_results_in_input_order():
    http = FakeHttp(delay=0.01)
    out = asyncio.run(fan_out.fetch_all(URLS, http.fetch, limit=10))
    assert out == [u.encode() for u in URLS]


def test_semaphore_caps_in_flight_requests():
    http = FakeHttp(delay=0.02)
    asyncio.run(fan_out.fetch_all(URLS, http.fetch, limit=10))
    assert http.peak == 10


def test_cap_sets_the_total_time():
    http = FakeHttp(delay=0.05)
    start = time.perf_counter()
    asyncio.run(fan_out.fetch_all(URLS, http.fetch, limit=10))
    assert 0.24 <= time.perf_counter() - start < 0.45  # 50 / 10 = 5 waves of 50 ms


def test_one_failure_cancels_the_rest_and_raises_exception_group():
    http = FakeHttp(delay=1.0, fail=URLS[3])
    with pytest.raises(ExceptionGroup) as info:
        asyncio.run(fan_out.fetch_all(URLS, http.fetch, limit=10))
    assert any(isinstance(e, ConnectionError) for e in info.value.exceptions)
    assert http.completed == 0  # nothing else finished: in-flight requests were cancelled
    assert len(http.cancelled) >= 9


def test_deadline_raises_timeout_error_and_cancels_work():
    http = FakeHttp(delay=5.0)
    start = time.perf_counter()
    with pytest.raises(TimeoutError):
        asyncio.run(fan_out.fetch_all(URLS, http.fetch, limit=10, deadline=0.1))
    assert time.perf_counter() - start < 0.5
    assert len(http.cancelled) == 10
