"""An audit row that must be written even when the shopper hangs up during the write."""

import asyncio

from audit import AuditStore
from spawn import spawn

ROW = "shopper-2 kettle-1l: seller-b at 1,199 after 250 ms"


async def plain(store):
    await store.write(ROW)  # cancelled with the handler


async def shielded(store):
    task = spawn(store.write(ROW), name="audit")  # owned: kept alive, failure logged
    await asyncio.shield(task)  # the handler can be cancelled; the write cannot be, by it


async def hang_up_during_write(handler, store):
    task = asyncio.create_task(handler(store))
    await asyncio.sleep(0.01)  # 10 ms into the 40 ms write, the shopper hangs up
    task.cancel()
    await asyncio.wait([task])
    print(f"  handler cancelled={task.cancelled()}; at 10 ms: rows={store.rows}")
    await asyncio.sleep(0.05)
    print(f"  at 60 ms: rows={len(store.rows)}, lost={len(store.lost)}")


async def stop_during_write(store):
    task = asyncio.create_task(shielded(store))
    await asyncio.sleep(0.01)
    task.cancel()  # the shopper hangs up, and main() returns: asyncio.run starts shutting down


async def main():
    print("-- 1. plain await: the shopper hangs up 10 ms into a 40 ms write --")
    await hang_up_during_write(plain, AuditStore(ms=40))
    print("-- 2. the write in an owned Task, awaited through shield() --")
    await hang_up_during_write(shielded, AuditStore(ms=40))


asyncio.run(main())
store = AuditStore(ms=40)
asyncio.run(stop_during_write(store))
print("-- 3. shield(), but the process shuts down 10 ms into the write --")
print(f"  after asyncio.run returned: rows={len(store.rows)}, lost={len(store.lost)}")
