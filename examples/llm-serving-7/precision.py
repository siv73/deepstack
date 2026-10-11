"""Bytes per stored number, and the low-precision Tensor Core peaks NVIDIA lists.

NVIDIA prints FP8 and INT8 Tensor Core figures "with sparsity"; an ordinary
forward pass gets half (the same rule Part 1 used for BF16). The A100 page
lists no FP8 row: Ampere has no FP8 Tensor Cores.
"""

from dataclasses import dataclass

BYTES = {"bf16": 2.0, "fp8": 1.0, "int8": 1.0, "int4": 0.5}

# GPU id -> sparse peak as printed by NVIDIA, in teraFLOPS (FP8) or TOPS (INT8). None = not listed.
FP8_SPARSE = {"a100-pcie": None, "h100-sxm": 3958, "h100-nvl": 3341, "h200-sxm": 3958}
INT8_SPARSE = {"a100-pcie": 1248, "h100-sxm": 3958, "h100-nvl": 3341, "h200-sxm": 3958}


@dataclass(frozen=True)
class Scheme:
    """How the weights are stored and which Tensor Core math the matrix multiplies use."""

    name: str
    weight: str  # key in BYTES
    math: str  # "bf16", "fp8" or "int8": the precision of the multiply itself


SCHEMES = {
    "bf16": Scheme("BF16 (no quantization)", "bf16", "bf16"),
    "fp8": Scheme("FP8 weights and activations (W8A8)", "fp8", "fp8"),
    "int8": Scheme("INT8 weights and activations (W8A8)", "int8", "int8"),
    "int4": Scheme("INT4 weights only (W4A16)", "int4", "bf16"),
}


def dense_ops(gpu_id: str, bf16_dense_flops: float, math: str) -> tuple[float, str]:
    """Dense peak for this multiply precision, and the precision actually used.

    FP8 math on a GPU without FP8 Tensor Cores falls back to weight-only (FP8 weights, BF16 math),
    which is what vLLM does on Ampere with its Marlin kernels.
    """
    if math == "fp8":
        if FP8_SPARSE[gpu_id] is None:
            return bf16_dense_flops, "bf16"
        return FP8_SPARSE[gpu_id] / 2 * 1e12, "fp8"
    if math == "int8":
        return INT8_SPARSE[gpu_id] / 2 * 1e12, "int8"
    return bf16_dense_flops, "bf16"
