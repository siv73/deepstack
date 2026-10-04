"""Raising work_mem multiplies across operations, workers and connections."""

from memory_budget import query_worst_case, server_worst_case


def test_one_query_with_two_hashes_and_a_sort():
    assert query_worst_case(work_mem_mb=4, sort_nodes=1, hash_nodes=2) == 4 + 2 * 4 * 2


def test_parallel_workers_each_get_the_limit():
    serial = query_worst_case(work_mem_mb=64, sort_nodes=1, hash_nodes=1)
    parallel = query_worst_case(work_mem_mb=64, sort_nodes=1, hash_nodes=1, workers=2)
    assert parallel == 3 * serial


def test_a_global_work_mem_raise_across_200_connections():
    total_mb = server_worst_case(200, work_mem_mb=256, sort_nodes=1, hash_nodes=2, workers=2)
    assert total_mb == 200 * 3 * (256 + 2 * 256 * 2)  # 768,000 MB: far beyond any server's RAM
