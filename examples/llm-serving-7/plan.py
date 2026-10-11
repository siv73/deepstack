"""Part 7's capacity planner: GPUs per replica, replicas for a target rate, colocated vs disaggregated.

For every TP size that fits, size each design for `rate` requests/s at `headroom` of its
best-case capacity, and keep the one that needs the fewest GPUs.
Usage: uv run plan.py h100-sxm llama-3.1-70b bf16 2000 300 1.0 0.1 20
"""

import math
import sys

from models import MODELS
from replica import colocated, decode_pool, prefill_pool
from tp import fit


def plan(gpu_id, m, dtype, prompt, output, ttft_slo, itl_slo, rate, headroom=0.8, link="nvlink",
         fixed_us=0.0, sizes=(1, 2, 4, 8)) -> dict:  # fmt: skip
    need = lambda per_replica: math.ceil(rate / (headroom * per_replica))  # noqa: E731
    rows = []
    for tp in sizes:
        if m.q_heads % tp or m.kv_heads % tp or fit(gpu_id, m, dtype, tp, prompt + output) < 1:
            continue
        row = {"tp": tp, "colocated": None, "disaggregated": None}
        col = colocated(gpu_id, m, dtype, tp, prompt, output, ttft_slo, itl_slo, fixed_us)
        if col:
            row["colocated"] = {**col, "replicas": need(col["rate"]), "gpus": tp * need(col["rate"])}
        pre = prefill_pool(gpu_id, m, dtype, tp, prompt, link, fixed_us=fixed_us)
        dec = decode_pool(gpu_id, m, dtype, tp, prompt, output, itl_slo, fixed_us)
        if dec:
            # wait for the step in progress, run the prompt, move its KV, then one decode step
            ttft = pre["step"] / 2 + pre["latency"] + pre["transfer"] + dec["itl"]
            if ttft <= ttft_slo:
                p, d = need(pre["rate"]), need(dec["rate"])
                row["disaggregated"] = {
                    **{"prefill": pre, "decode": dec, "ttft": ttft},
                    **{"prefill_replicas": p, "decode_replicas": d, "gpus": tp * (p + d)},
                }
        rows.append(row)

    def best(kind):
        ok = [r for r in rows if r[kind]]
        return min(ok, key=lambda r: (r[kind]["gpus"], r["tp"])) if ok else None

    return {"rows": rows, "colocated": best("colocated"), "disaggregated": best("disaggregated")}


if __name__ == "__main__":
    gpu_id, m, dtype = sys.argv[1], MODELS[sys.argv[2]], sys.argv[3]
    prompt, output = int(sys.argv[4]), int(sys.argv[5])
    ttft_slo, itl_slo, rate = float(sys.argv[6]), float(sys.argv[7]), float(sys.argv[8])
    p = plan(gpu_id, m, dtype, prompt, output, ttft_slo, itl_slo, rate)
    for kind in ("colocated", "disaggregated"):
        b = p[kind]
        print(f"{kind}: " + (f"TP={b['tp']}, {b[kind]['gpus']} GPUs" if b else "cannot meet the targets"))
