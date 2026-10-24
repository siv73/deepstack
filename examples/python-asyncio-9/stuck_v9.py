"""Rung 1: gateway v9 with an audit store that stops answering. What does each signal say?"""

import incident
from observe import LagMonitor
from request_log import capture

lines = capture("gateway", "seller_e_sdk")  # gateway v8's text log lines, with the request id


async def look(gateway):
    lag = LagMonitor(every=0.05)
    lag.start()
    lines.lines.clear()  # only what is logged while the 5 shoppers wait
    await incident.asyncio.sleep(0.5)
    await lag.stop()
    await gateway.metrics.flush()  # what the metrics service has for all 10 requests so far
    errors = [line for line in lines.lines if "ERROR" in line or "WARNING" in line]
    return [
        f"log lines while they wait: {len(lines.lines)}; errors or warnings: {len(errors)}",
        f"seller outcomes on the dashboard: {gateway.metrics.sink.totals()}",
        f"loop lag, worst in 500 ms: {round(lag.take_worst() / 10) * 10} ms",
        f"requests in progress: {gateway.in_progress}; audit rows waiting in the queue: "
        f"{gateway.audit_queue.queue.qsize()}",
    ]


if __name__ == "__main__":  # the process pool's workers import this file too
    report, seen, _ = incident.main(look)
    print(report[0])
    print("-- the audit store stops answering; 5 more shoppers, each waits up to 2 s --")
    print("\n".join(seen))
    print(report[1])
