"""A Future: a box that is empty now and gets a result, an exception, or a cancel later."""

import asyncio

from sellers import Offer, SellerError

loop = asyncio.new_event_loop()


def show(label, fut):
    print(f"{label:<24} done={fut.done()!s:<5} cancelled={fut.cancelled()}")


fut = loop.create_future()
show("1. new Future:", fut)
try:
    fut.result()
except asyncio.InvalidStateError:
    print("   result() too early -> InvalidStateError")

fut.add_done_callback(lambda f: print(f"   done callback got {f.result()}"))
fut.set_result(Offer("seller-b", 1199))
show("2. after set_result:", fut)
print("   (the callback has not run yet: it was scheduled with call_soon)")
loop.call_soon(loop.stop)
loop.run_forever()  # one loop iteration runs the scheduled callback

try:
    fut.set_result(Offer("seller-a", 1249))
except asyncio.InvalidStateError:
    print("   a second set_result -> InvalidStateError")

failed = loop.create_future()
failed.set_exception(SellerError("seller-c failed"))
show("3. after set_exception:", failed)
print(f"   exception() returns {failed.exception()!r}")

gone = loop.create_future()
print(f"   cancel() returns {gone.cancel()}")
show("4. after cancel:", gone)
try:
    gone.result()
except asyncio.CancelledError:
    print("   result() -> CancelledError")
loop.close()
