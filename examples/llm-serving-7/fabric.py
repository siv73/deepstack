"""Link speeds between GPUs, as NVIDIA prints them, turned into bytes per second each way.

NVLink: NVIDIA's 900 GB/s for H100 and H200 SXM is a total; Hopper has 18 links at
25 GB/s each direction, so 450 GB/s each way. Network: a DGX H100 has eight 400 Gb/s
ConnectX-7 cards for eight GPUs, so about 50 GB/s each way per GPU.
"""

NVLINK_TOTAL_GB_S = {"h100-sxm": 900, "h200-sxm": 900}  # as printed on the spec pages
NVLINK_LINKS, NVLINK_LINK_GB_S_EACH_WAY = 18, 25  # Hopper architecture whitepaper blog
NIC_GBIT_S = 400  # ConnectX-7, DGX H100


def nvlink_each_way(gpu_id: str) -> float:
    assert NVLINK_TOTAL_GB_S[gpu_id] == 2 * NVLINK_LINKS * NVLINK_LINK_GB_S_EACH_WAY  # both directions
    return NVLINK_LINKS * NVLINK_LINK_GB_S_EACH_WAY * 1e9  # bytes/s


def nic_each_way() -> float:
    return NIC_GBIT_S / 8 * 1e9  # bytes/s per GPU


LINKS = {"nvlink": nvlink_each_way, "network": lambda gpu_id: nic_each_way()}
