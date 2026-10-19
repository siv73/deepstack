"""Gateway v1: the five seller waits overlap on the toy loop, on one thread."""

from sellers import BUDGET_MS, SELLERS, Offer, SellerError, cheapest
from toyloop import ToyLoop, sleep


async def ask_seller(loop, seller, item, faulty=()):
    await sleep(seller.latency_ms)  # the network wait, faked with a timer
    if seller.name in faulty:
        raise SellerError(f"{seller.name} failed")
    print(f"{loop.now:5} ms  {seller.name} answered {seller.price:,}")
    return Offer(seller.name, seller.price)


def compare(item, budget_ms=None, faulty=(), ask=ask_seller):
    loop = ToyLoop()
    tasks = [loop.spawn(ask(loop, s, item, faulty), s.name) for s in SELLERS]
    loop.run(until=budget_ms)
    offers = [t.result for t in tasks if t.done]
    missed = [t.name for t in tasks if not t.done]
    for t in tasks:
        if not t.done:
            t.coro.close()  # GeneratorExit at its await: it stops waiting
    best = cheapest(offers)
    return best, missed, loop


def report(best, missed, loop):
    answer = f"{best.seller} at {best.price:,}" if best else "none"
    line = f"cheapest: {answer} after {loop.now:,} ms"
    if missed:
        line += "; missed: " + ", ".join(missed)
    print(line)
    for warning in loop.warnings:
        print(warning)


if __name__ == "__main__":
    print("-- wait for every seller --")
    report(*compare("kettle-1l"))
    print(f"-- stop at the {BUDGET_MS} ms budget --")
    report(*compare("kettle-1l", budget_ms=BUDGET_MS))
