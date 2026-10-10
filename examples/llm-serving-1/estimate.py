"""Roofline estimate of prefill and decode time for a dense model in BF16.

Counts only the weights: 2 FLOPs per parameter per token, 2 bytes per
parameter read once per forward pass. Attention's own reads (the KV cache)
are left out; Part 2 adds them. Usage: uv run estimate.py h100-sxm 8 2000 300
"""

import sys

from gpus import GPU, GPUS

BYTES_PER_PARAM = 2  # BF16


def forward_pass(gpu: GPU, params: float, tokens: int) -> tuple[float, str]:
    """Seconds for one forward pass over `tokens` tokens, and which limit sets it."""
    compute_s = 2 * params * tokens / gpu.peak_flops
    memory_s = params * BYTES_PER_PARAM / gpu.bandwidth
    return max(compute_s, memory_s), "compute" if compute_s > memory_s else "memory"


def estimate(gpu: GPU, params: float, prompt: int, output: int, batch: int = 1) -> dict:
    prefill_s, prefill_bound = forward_pass(gpu, params, prompt * batch)
    step_s, decode_bound = forward_pass(gpu, params, batch)  # one new token per request
    return {
        "fits": params * BYTES_PER_PARAM <= gpu.memory_gb * 1e9,
        "ttft_s": prefill_s,  # with an empty queue
        "prefill_bound": prefill_bound,
        "tpot_s": step_s,
        "decode_bound": decode_bound,
        "e2e_s": prefill_s + step_s * (output - 1),
        "decode_tokens_per_s": batch / step_s,
        "ridge_flops_per_byte": gpu.peak_flops / gpu.bandwidth,
    }


if __name__ == "__main__":
    gpu_id, billions, prompt, output = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    for key, value in estimate(GPUS[gpu_id], billions * 1e9, prompt, output).items():
        print(f"{key:>22}: {value:.4g}" if isinstance(value, float) else f"{key:>22}: {value}")
