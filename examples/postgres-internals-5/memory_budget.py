"""Worst-case memory for sorts and hashes: work_mem is a per-operation limit, not per query."""


def query_worst_case(work_mem_mb, sort_nodes, hash_nodes, hash_mem_multiplier=2.0, workers=0):
    """Each sort may use work_mem; each hash work_mem * hash_mem_multiplier; every process gets its own."""
    per_process = sort_nodes * work_mem_mb + hash_nodes * work_mem_mb * hash_mem_multiplier
    return per_process * (workers + 1)  # the leader runs the plan too


def server_worst_case(active_queries, **query):
    return active_queries * query_worst_case(**query)
