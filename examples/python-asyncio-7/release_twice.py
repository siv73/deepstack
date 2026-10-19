"""One release() too many: Lock, Semaphore(1) and BoundedSemaphore(1) answer differently."""

import asyncio


async def main():
    lock = asyncio.Lock()
    await lock.acquire()
    lock.release()
    try:
        lock.release()
    except RuntimeError as e:
        print(f"Lock, released twice:              RuntimeError: {e}")

    sem = asyncio.Semaphore(1)
    await sem.acquire()
    sem.release()
    sem.release()  # no error
    await sem.acquire()
    print(f"Semaphore(1), released twice:      no error; after one acquire, locked() = {sem.locked()}")

    bounded = asyncio.BoundedSemaphore(1)
    await bounded.acquire()
    bounded.release()
    try:
        bounded.release()
    except ValueError as e:
        print(f"BoundedSemaphore(1), released twice: ValueError: {e}")

    other = asyncio.Lock()
    await other.acquire()  # taken by main()

    async def someone_else():
        other.release()  # a different Task may release it

    await asyncio.create_task(someone_else())
    print(f"Lock released by another Task:     allowed; locked() = {other.locked()}")


if __name__ == "__main__":
    asyncio.run(main())
