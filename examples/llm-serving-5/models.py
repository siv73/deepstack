"""Attention shapes of a few dense models, as Meta's reference code defines them.

Llama 3.1 values: meta-llama/llama-models (models/sku_list.py), cross-checked
against Table 3 of "The Llama 3 Herd of Models". head_dim = dim // n_heads.
The MHA and MQA rows are hypothetical variants of the 8B model, for comparison.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    name: str
    params: float  # parameter count, used for weight bytes and FLOPs
    layers: int
    q_heads: int  # attention (query) heads
    kv_heads: int  # key/value heads: = q_heads is MHA, 1 is MQA, in between is GQA
    head_dim: int

    @property
    def group_size(self) -> int:
        """Query heads sharing one key/value head."""
        return self.q_heads // self.kv_heads


MODELS = {
    "llama-3.1-8b": Model("Llama 3.1 8B", 8e9, layers=32, q_heads=32, kv_heads=8, head_dim=4096 // 32),
    "llama-3.1-70b": Model("Llama 3.1 70B", 70e9, layers=80, q_heads=64, kv_heads=8, head_dim=8192 // 64),
    "8b-as-mha": Model("8B with MHA (hypothetical)", 8e9, layers=32, q_heads=32, kv_heads=32, head_dim=128),
    "8b-as-mqa": Model("8B with MQA (hypothetical)", 8e9, layers=32, q_heads=32, kv_heads=1, head_dim=128),
}
