"""except*: handle each kind of failure inside the ExceptionGroup a TaskGroup raises."""

import asyncio

from sellers import Offer, SellerError


async def seller(name, outcome):
    await asyncio.sleep(0)
    if isinstance(outcome, Exception):
        raise outcome
    return Offer(name, outcome)


async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(seller("seller-a", 1249))
            tg.create_task(seller("seller-c", SellerError("seller-c failed")))
            tg.create_task(seller("seller-d", ConnectionRefusedError("seller-d refused")))
            tg.create_task(seller("seller-b", SellerError("seller-b failed")))
    except* SellerError as group:
        print("except* SellerError got:", [str(e) for e in group.exceptions])
    except* OSError as group:
        print("except* OSError got:", [str(e) for e in group.exceptions])
    print("both clauses ran; nothing is left to propagate")

    try:
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(seller("seller-c", SellerError("seller-c failed")))
                tg.create_task(seller("seller-e", ValueError("bad price 'abc'")))
        except* SellerError as group:
            print("handled:", [str(e) for e in group.exceptions])
    except ExceptionGroup as rest:
        print("left over and raised again:", rest.exceptions)


if __name__ == "__main__":
    asyncio.run(main())
