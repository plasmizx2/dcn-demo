"""
Resource guard — prevents heavy tasks from crashing the machine.

Limits CPU parallelism (leaves cores for OS) and checks available memory
before compute-intensive operations.
"""

import os


def safe_n_jobs():
    """Return a safe n_jobs value that leaves 2 cores free for the OS."""
    cores = os.cpu_count() or 1
    safe = max(1, cores - 2)
    return safe


def safe_dataset_size(n_rows, ram_gb=None):
    """
    Return max rows to use based on available RAM.
    Heavy sklearn models (RF, GB with 500 trees) need ~1GB per 25K rows.
    """
    if ram_gb is None:
        try:
            import psutil
            ram_gb = psutil.virtual_memory().available / (1024 ** 3)
        except ImportError:
            return n_rows  # Can't check, use full dataset

    # Conservative: allow ~25K rows per GB of available RAM
    max_rows = int(ram_gb * 25_000)
    max_rows = max(5_000, max_rows)  # Floor at 5K rows

    if n_rows > max_rows:
        return max_rows
    return n_rows
