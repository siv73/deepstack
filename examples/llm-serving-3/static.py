"""Static (request-level) batching: wait for a full batch, pad, run it until the slowest request ends."""

from gpus import GPU
from models import Model
from step import step_seconds
from workload import Request


def run_static(reqs: list[Request], gpu: GPU, m: Model, max_batch: int) -> dict:
    t = busy = 0.0
    useful = processed = 0  # token-rows that did real work vs all token-rows the GPU ran
    for i in range(0, len(reqs), max_batch):
        batch = reqs[i : i + max_batch]
        t = max(t, batch[-1].arrival)  # GPU sits idle until the batch is full (or the trace ends)
        start, pad, longest = t, max(r.prompt for r in batch), max(r.output for r in batch)
        t += step_seconds(gpu, m, [pad] * len(batch), [])  # every prompt padded to the longest
        for r in batch:
            r.first = t
        for k in range(1, longest):  # every row runs until the longest output is done
            dt = step_seconds(gpu, m, [], [pad + k] * len(batch))
            t += dt
            for r in batch:
                if k < r.output:
                    r.last, r.max_gap = t, max(r.max_gap, dt)
        for r in batch:
            r.last = r.last if r.output > 1 else r.first
            r.done = t  # the whole batch returns together
        busy += t - start
        useful += sum(r.prompt + r.output - 1 for r in batch)
        processed += len(batch) * (pad + longest - 1)
    return {"busy": busy, "padding_fraction": 1 - useful / processed, "preemptions": 0}
