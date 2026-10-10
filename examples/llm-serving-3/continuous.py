"""Continuous (iteration-level) batching, shaped like vLLM's scheduler with chunked prefill off.

Every step: running requests decode one token each; if nothing was preempted, waiting requests
join first come, first served while a slot (max_num_seqs), the token budget
(max_num_batched_tokens) and the KV budget allow. Finished requests leave after the step.
"""

from collections import deque

from gpus import GPU
from models import Model
from step import step_seconds


def run_continuous(reqs, gpu: GPU, m: Model, max_num_seqs: int, max_num_batched_tokens: int,
                   kv_tokens: float = float("inf")) -> dict:  # fmt: skip
    assert max(r.prompt + r.output for r in reqs) <= max_num_batched_tokens, "no chunking here"
    t = busy = 0.0
    arrivals, waiting, running = deque(reqs), deque(), []  # running: [request, cached tokens, made]
    preemptions = 0
    while arrivals or waiting or running:
        while arrivals and arrivals[0].arrival <= t:
            waiting.append([arrivals.popleft(), 0, 0])
        if not waiting and not running:
            t = arrivals[0].arrival  # nothing to do: the GPU idles until the next arrival
            continue
        preempted = False
        while sum(s[1] + 1 for s in running) > kv_tokens:  # no room for one more token each
            victim = running.pop()  # the most recently admitted request loses its cache
            victim[1], preempted = 0, True
            victim[0].preempted += 1
            preemptions += 1
            waiting.appendleft(victim)
        budget, new = max_num_batched_tokens - len(running), []
        kv_used = sum(s[1] + 1 for s in running)
        while not preempted and waiting and len(running) + len(new) < max_num_seqs:
            r, _, made = waiting[0]
            need = r.prompt + made  # a preempted request recomputes its prompt and its output so far
            if need > budget or kv_used + need > kv_tokens:
                break
            budget, kv_used = budget - need, kv_used + need
            new.append(waiting.popleft())
        dt = step_seconds(gpu, m, [s[0].prompt + s[2] for s in new], [s[1] for s in running])
        t, busy = t + dt, busy + dt
        for s in running:
            s[1], s[2] = s[1] + 1, s[2] + 1
            s[0].max_gap = max(s[0].max_gap, t - s[0].last)
            s[0].last = t
        for s in new:
            s[1], s[2] = s[0].prompt + s[2], s[2] + 1
            if s[2] == 1:
                s[0].first = t
            else:
                s[0].max_gap = max(s[0].max_gap, t - s[0].last)
            s[0].last = t
        running += new
        for s in [s for s in running if s[2] == s[0].output]:
            s[0].done = t  # each request returns the moment it finishes
            running.remove(s)
    return {"busy": busy, "padding_fraction": 0.0, "preemptions": preemptions}
