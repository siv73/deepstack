"""Retry the whole transaction on serialization failure or deadlock (PostgreSQL 18 docs, 13.5)."""

import random
import time

RETRYABLE = {"40001", "40P01"}  # serialization_failure, deadlock_detected


def run_transaction(conn, work, attempts=5, base_delay=0.05, sleep=time.sleep):
    """Run work(conn) and commit. Reads AND decisions live inside work, so a retry re-decides."""
    for attempt in range(1, attempts + 1):
        try:
            result = work(conn)
            conn.commit()  # inside the try: the failure may come from any statement
            return result
        except Exception as e:
            conn.rollback()
            if getattr(e, "sqlstate", None) not in RETRYABLE or attempt == attempts:
                raise
            sleep(base_delay * 2 ** (attempt - 1) * random.random())  # backoff with jitter
    raise AssertionError("unreachable")
