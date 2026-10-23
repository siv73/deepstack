"""A one-test file with a forgotten await. test_page4.py runs pytest on it with four warning settings.

Its name does not start with test_, so the normal test run does not collect it.
"""

import asyncio
import gc


async def save_receipt():
    pass


def test_checkout():
    async def checkout():
        save_receipt()  # forgotten await

    asyncio.run(checkout())
    gc.collect()
