"""Statistics over whole milliseconds, in Python: the report needs a few thousand values at most, and SQLite (the
tests) has no percentile_cont. Pure."""
from typing import Optional, Sequence


def percentile(values: Sequence[int], p: float) -> Optional[int]:
    """Linear interpolation between the closest ranks (numpy's default method); None without values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (rank - low))


def mean(values: Sequence[int]) -> Optional[int]:
    return round(sum(values) / len(values)) if values else None
