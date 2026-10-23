"""await passes the innermost yield all the way out to whoever called send()."""

from toyloop import Sleep


async def fetch_price():
    await Sleep(80)  # Sleep.__await__ yields ("sleep", 80)
    return 1249


async def handle_request():
    price = await fetch_price()
    return f"price {price:,}"


coro = handle_request()
request = coro.send(None)  # runs handle_request -> fetch_price -> Sleep, then pauses
print("loop received:", request)
try:
    coro.send(None)  # 80 ms later the loop resumes it; it runs to the end
except StopIteration as stop:
    print("finished with:", stop.value)
