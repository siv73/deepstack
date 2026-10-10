"""Dense BF16 peak and memory figures for a few NVIDIA data-center GPUs.

NVIDIA lists BF16 Tensor Core throughput "with sparsity"; the dense figure,
which an ordinary forward pass gets, is half of it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GPU:
    name: str
    bf16_sparse_tflops: float  # as printed on NVIDIA's spec page
    hbm_tb_per_s: float  # memory bandwidth, terabytes per second
    memory_gb: float

    @property
    def peak_flops(self) -> float:
        return self.bf16_sparse_tflops / 2 * 1e12  # dense FLOP/s

    @property
    def bandwidth(self) -> float:
        return self.hbm_tb_per_s * 1e12  # bytes/s


GPUS = {
    "a100-pcie": GPU("A100 80GB PCIe", 624, 1.935, 80),
    "h100-sxm": GPU("H100 SXM", 1979, 3.35, 80),
    "h100-nvl": GPU("H100 NVL", 1671, 3.9, 94),
    "h200-sxm": GPU("H200 SXM", 1979, 4.8, 141),
}
