"""Testing async code with only the standard library."""

import asyncio
import unittest

import stock


class StockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.stock = stock.Stock(1)  # a fresh event loop per test

    async def test_only_one_reservation_wins(self) -> None:
        results = await asyncio.gather(*(self.stock.reserve_safe() for _ in range(5)))
        self.assertEqual(sum(results), 1)

    async def test_no_tasks_leak(self) -> None:
        await self.stock.reserve_safe()
        others = asyncio.all_tasks() - {asyncio.current_task()}
        self.assertEqual(others, set())  # nothing left running in the background
