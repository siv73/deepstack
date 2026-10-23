"""Work in = work out: the gateway's numbers during seller-c's outage in a sale.

Each stage holds (arrival rate) x (time each request spends there) requests at once.
A stage with a deadline caps that time; a stage without one grows by (in - out) every second.
"""

KB_PER_REQUEST = 7  # measured by request_cost.py: a waiting request's connection, buffers and Task
ARRIVALS = 3_000  # requests per second once shoppers start refreshing
CAPACITY = 2_000  # ranking: 2 worker processes x 1 ms of CPU per request (Part 4)
SELLER_STAGE_S = 0.25  # every seller call is cut by the 250 ms deadline
IN_GATEWAY_S = 0.28  # a request that is served: sellers, ranking, counts, audit row


def mb(requests):
    return requests * KB_PER_REQUEST / 1024


def main():
    print(f"arrivals {ARRIVALS:,}/s, ranking finishes {CAPACITY:,}/s")
    sellers = ARRIVALS * SELLER_STAGE_S
    print(f"seller stage: {ARRIVALS:,} x {SELLER_STAGE_S} s = {sellers:,.0f} requests, the same every minute")
    print("ranking line, no deadline:")
    print("  minute   waiting   memory     a new request waits")
    for minute in (0, 1, 2, 5, 10):
        waiting = (ARRIVALS - CAPACITY) * minute * 60
        wait_s = waiting / CAPACITY
        print(f"  {minute:>6}   {waiting:>7,}   {mb(waiting):>7,.0f} MB   {wait_s:>5,.0f} s")
    admitted = CAPACITY * IN_GATEWAY_S
    print("shedding at the door, only what can be finished is admitted:")
    print(f"  in progress: {CAPACITY:,} x {IN_GATEWAY_S} s = {admitted:,.0f} requests, {mb(admitted):.1f} MB")
    print(f"  refused at once: {ARRIVALS - CAPACITY:,}/s, each told 'busy' before any work is done")


if __name__ == "__main__":
    main()
