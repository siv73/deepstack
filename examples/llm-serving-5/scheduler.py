"""A vLLM-shaped scheduler loop: token budget, chunked prefill, FCFS or priority, preemption.

Each step: running requests first, in order, each taking what it still needs (one token for a
decode) from the max_num_batched_tokens budget; then, if nothing was preempted, waiting requests
in queue order while budget, slots and KV room last. With chunked prefill a prompt that does not
fit takes what is left of the budget and continues next step. Shaped like vLLM v0.31.0's
Scheduler.schedule(); speculative decoding, prefix caching and async scheduling are left out.
"""

from dataclasses import dataclass, field

from step import step_seconds


@dataclass
class Req:
    arrival: float
    prompt: int
    output: int
    priority: int = 0  # lower runs first under the priority policy, as in vLLM
    tenant: str = "a"
    cached: int = 0  # tokens whose keys and values are in the cache
    made: int = 0  # output tokens produced
    scheduled: float = -1.0  # when it first left the waiting queue
    first: float = 0.0
    last: float = 0.0
    done: float = 0.0
    gaps: list[float] = field(default_factory=list)  # time between its own tokens (ITL)
    preempted: int = 0
    rejected: bool = False


def run(reqs, gpu, m, budget=8192, max_seqs=1024, kv_tokens=float("inf"), chunked=True,
        policy="fcfs", long_prefill=0, max_queued=None, running=None) -> dict:  # fmt: skip
    arrivals = sorted(reqs, key=lambda r: r.arrival)
    running, waiting, steps, preemptions, t = list(running or []), [], [], 0, 0.0
    order = (lambda r: (r.priority, r.arrival)) if policy == "priority" else None
    while arrivals or waiting or running:
        while arrivals and arrivals[0].arrival <= t:
            r = arrivals.pop(0)
            r.rejected = max_queued is not None and len(waiting) + len(running) >= max_queued
            if not r.rejected:  # vLLM answers HTTP 503 when max_num_queued_reqs is reached
                waiting.append(r)
        if not waiting and not running:
            t = arrivals[0].arrival  # idle until the next arrival
            continue
        cap = long_prefill if len(waiting) + len(running) > 1 else 0
        left, sched, used, i = budget, [], sum(r.cached for r in running), 0
        preempted = False
        while i < len(running) and left > 0:  # 1. running requests, in admission order
            r = running[i]
            n = min(r.prompt + r.made - r.cached, cap or budget, left)
            while used + n > kv_tokens:  # no room: preempt a victim and recompute it later
                v = max(running, key=order) if order else running[-1]
                i -= running.index(v) < i
                running.remove(v)
                for s in [s for s in sched if s[0] is v]:  # give back what it was given
                    sched.remove(s)
                    left, used = left + s[1], used - s[1]
                used, v.cached, preempted = used - v.cached, 0, True
                v.preempted, preemptions = v.preempted + 1, preemptions + 1
                waiting.insert(0, v)  # its cache is gone: prompt and output so far are redone
                if v is r:
                    break
            if r not in running:
                continue
            sched.append((r, n))
            left, used, i = left - n, used + n, i + 1
        while not preempted and waiting and left > 0 and len(running) < max_seqs:  # 2. admit
            r = min(waiting, key=order) if order else waiting[0]
            need = min(r.prompt + r.made, cap or budget)
            if (not chunked and need > left) or used + r.prompt + r.made > kv_tokens:
                break  # the head of the queue does not fit: nobody behind it may pass
            waiting.remove(r)
            running.append(r)
            r.scheduled = t if r.scheduled < 0 else r.scheduled
            sched.append((r, min(need, left)))
            left, used = left - min(need, left), used + min(need, left)
        assert sched, "a single request does not fit the KV cache"
        decodes = [r.cached for r, n in sched if n == 1 and r.cached == r.prompt + r.made - 1]
        chunks = [(r.cached, n) for r, n in sched if not (n == 1 and r.cached == r.prompt + r.made - 1)]
        dt = step_seconds(gpu, m, chunks, decodes)
        t += dt
        steps.append({"dt": dt, "decode": len(decodes), "prefill": sum(c for _, c in chunks),
                      "waiting": len(waiting), "kv_used": used})  # fmt: skip
        for r, n in sched:
            r.cached += n
            if r.cached == r.prompt + r.made:  # whole input processed: one new token
                r.made += 1
                if r.made == 1:
                    r.first = t
                else:
                    r.gaps.append(t - r.last)
                r.last = t
                if r.made == r.output:
                    r.done = t
                    running.remove(r)
    return {"steps": steps, "preemptions": preemptions, "end": t}
