"""What travels up an await chain in asyncio: the Future object itself.

Same experiment as Part 1's await_chain.py, with no loop: we drive the coroutine by hand.
"""

import asyncio

loop = asyncio.new_event_loop()
fut = loop.create_future()


async def ask_seller_b():
    price = await fut  # Future.__await__ yields the Future, then returns its result
    return f"price {price:,}"


coro = ask_seller_b()
yielded = coro.send(None)  # run until the first suspension
print(f"yielded: {type(yielded).__name__}; it is our Future: {yielded is fut}")
fut.set_result(1199)  # what a timer or a socket callback would do
try:
    coro.send(None)  # resume it: the await now returns the result
except StopIteration as stop:
    print(f"finished with: {stop.value}")
loop.close()
