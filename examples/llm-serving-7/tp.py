"""How many GPUs one replica needs: split the weights t ways and see what is left for the KV cache.

Usage: uv run tp.py h100-sxm llama-3.1-70b bf16 2000 300
"""

import math
import sys

from gpus import GPUS
from kv_cache import kv_bytes_per_token
from models import MODELS, Model
from precision import BYTES


def kv_budget(gpu_id: str, m: Model, dtype: str, tp: int, util=0.92, reserve_gb=3.0) -> float:
    """KV cache bytes across the whole tensor-parallel group, after weights and reserve."""
    per_gpu = GPUS[gpu_id].memory_gb * 1e9 * util - reserve_gb * 1e9 - m.params * BYTES[dtype] / tp
    return tp * per_gpu if per_gpu > 0 else 0.0


def fit(gpu_id: str, m: Model, dtype: str, tp: int, tokens_per_request: int) -> int:
    """Requests of this length whose KV cache fits in the group at once."""
    per_token = kv_bytes_per_token(m, int(BYTES[dtype]))  # all KV heads; TP splits them t ways
    return math.floor(kv_budget(gpu_id, m, dtype, tp) / (tokens_per_request * per_token))


def smallest_tp(gpu_id: str, m: Model, dtype: str, tokens_per_request: int, sizes=(1, 2, 4, 8)):
    """Smallest TP size (dividing the attention heads) that holds at least one full request."""
    for tp in sizes:
        if m.q_heads % tp == 0 and m.kv_heads % tp == 0 and fit(gpu_id, m, dtype, tp, tokens_per_request):
            return tp
    return None


if __name__ == "__main__":
    gpu_id, m, dtype = sys.argv[1], MODELS[sys.argv[2]], sys.argv[3]
    n = int(sys.argv[4]) + int(sys.argv[5])  # prompt + output tokens
    for tp in (1, 2, 4, 8):
        gb, fits = kv_budget(gpu_id, m, dtype, tp) / 1e9, fit(gpu_id, m, dtype, tp, n)
        print(f"TP={tp}: KV budget {gb:6.1f} GB, {fits:>5} requests")
    print(f"Smallest TP that fits: {smallest_tp(gpu_id, m, dtype, n)}")
