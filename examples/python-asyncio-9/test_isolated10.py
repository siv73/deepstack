"""The same style with the standard library only: IsolatedAsyncioTestCase on the virtual clock (3.13+)."""

import asyncio
import sys
import unittest

from gateway_v9 import Budget
from stubs import connection, make_gateway
from virtual_clock import VirtualClockLoop


@unittest.skipIf(sys.version_info < (3, 13), "loop_factory on IsolatedAsyncioTestCase is new in 3.13")
class GatewayTests(unittest.IsolatedAsyncioTestCase):
    loop_factory = VirtualClockLoop  # a fresh virtual-clock loop for every test method

    async def asyncSetUp(self):
        self.gateway = make_gateway()
        await self.gateway.start()

    async def asyncTearDown(self):
        await self.gateway.shutdown([], Budget())
        left = asyncio.all_tasks() - {asyncio.current_task()}
        self.assertEqual(left, set())  # the runner would cancel leftovers silently; fail on them instead

    async def test_two_requests_for_one_item_make_one_call_per_seller(self):
        readers = [connection(f"shop-{n} kettle-1l") for n in (1, 2)]
        await asyncio.gather(*(self.gateway.serve(r, w) for r, w in readers))
        self.assertEqual([w.sent for _, w in readers], [["seller-b 1199\n"]] * 2)
        self.assertEqual(len(self.gateway.stubs.calls), 5)  # Part 7's single-flight, not 10 calls

    async def test_the_loop_is_in_debug_mode_and_its_clock_starts_at_zero(self):
        loop = asyncio.get_running_loop()
        self.assertTrue(loop.get_debug())  # IsolatedAsyncioTestCase turns debug mode on
        self.assertEqual(loop.time(), 0.0)
