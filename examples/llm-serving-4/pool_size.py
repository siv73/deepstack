"""How vLLM v0.31.0 turns gpu_memory_utilization into a number of KV blocks (simplified).

KV memory = total x gpu_memory_utilization - everything else the profile run measured
(weights, peak activations, other). Blocks = KV memory // bytes per block, where one block
holds block_size tokens of keys and values for every layer. "Everything else" is an input
here (weights in BF16 plus a reserve), because only a real profile run can measure it.
"""

from gpus import GPU
from models import Model

BF16 = 2


def bytes_per_block(m: Model, block_size: int = 16, dtype_bytes: int = BF16) -> int:
    per_layer = m.kv_heads * block_size * (m.head_dim + m.head_dim) * dtype_bytes  # keys + values
    return m.layers * per_layer


def num_blocks(gpu: GPU, m: Model, util: float = 0.92, reserve_gb: float = 3.0, block_size: int = 16) -> int:
    kv_memory = gpu.memory_gb * 1e9 * util - m.params * BF16 - reserve_gb * 1e9
    return max(0, int(kv_memory // bytes_per_block(m, block_size)))
