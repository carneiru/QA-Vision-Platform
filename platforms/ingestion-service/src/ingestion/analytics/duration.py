"""Suite duration prediction (POST /analytics/duration-estimate): pure helpers over rows the service read.

Per test: the typical duration is the median of its passed executions (else of its non-skipped ones), the
upper one the p90 of every non-skipped execution, so timeouts count. Per project: the last runs fit
`wall ~ overhead + factor * serial`, which turns a sum of test durations into a wall-clock time
(parallel workers make factor < 1; setup and teardown are the overhead)."""
import math
from dataclasses import dataclass
from statistics import median
from typing import Iterable, List, Optional, Sequence, Tuple

ENVIRONMENT_MIN_EXECUTIONS = 3
MIN_FIT_POINTS = 5
MIN_FACTOR, MAX_FACTOR = 0.05, 1.0
MAX_OVERHEAD_MS = 30 * 60 * 1000


@dataclass(frozen=True)
class Execution:
    status: str
    duration_ms: int
    environment: Optional[str]


@dataclass(frozen=True)
class Model:
    overhead_ms: int
    factor: float
    runs: int
    fitted: bool


# (typical_ms, upper_ms, environment_used), or None for a test without history
Durations = Optional[Tuple[float, float, bool]]


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Linear interpolation between the closest ranks (numpy's default); None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def durations_for(executions: Iterable[Execution], environment: Optional[str]) -> Durations:
    ran = [e for e in executions if e.status != "skipped"]
    used_env = False
    if environment:
        there = [e for e in ran if e.environment == environment]
        if len(there) >= ENVIRONMENT_MIN_EXECUTIONS:
            ran, used_env = there, True
    if not ran:
        return None
    passed = [e.duration_ms for e in ran if e.status == "passed"]
    every = [e.duration_ms for e in ran]
    typical = percentile(passed or every, 0.5)
    # A test whose failures are fast (an early assertion) could get an upper bound below its typical time
    upper = max(percentile(every, 0.9), typical)
    return typical, upper, used_env


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fallback(points: List[Tuple[float, float]]) -> Model:
    ratios = [wall / serial for serial, wall in points if serial > 0]
    factor = _clamp(median(ratios), MIN_FACTOR, MAX_FACTOR) if ratios else 1.0
    return Model(overhead_ms=0, factor=factor, runs=len(points), fitted=False)


def fit_model(points: Sequence[Tuple[float, float]]) -> Model:
    """points: (serial_ms, wall_ms) per run. Ordinary least squares from MIN_FIT_POINTS points, clamped;
    otherwise (or on a negative or undefined slope) no overhead and the median wall/serial ratio."""
    points = [(float(s), float(w)) for s, w in points]
    if len(points) < MIN_FIT_POINTS:
        return _fallback(points)
    n = len(points)
    mean_x = sum(s for s, _ in points) / n
    mean_y = sum(w for _, w in points) / n
    var = sum((s - mean_x) ** 2 for s, _ in points)
    if var == 0:
        return _fallback(points)
    slope = sum((s - mean_x) * (w - mean_y) for s, w in points) / var
    if not math.isfinite(slope) or slope < 0:
        return _fallback(points)
    intercept = mean_y - slope * mean_x
    return Model(overhead_ms=round(_clamp(intercept, 0, MAX_OVERHEAD_MS)),
                 factor=_clamp(slope, MIN_FACTOR, MAX_FACTOR), runs=n, fitted=True)


def combine(per_test: Sequence[Durations], model: Model) -> dict:
    known = [d for d in per_test if d is not None]
    estimate = upper = None
    if known:
        estimate = round(model.overhead_ms + model.factor * sum(d[0] for d in known))
        upper = round(model.overhead_ms + model.factor * sum(d[1] for d in known))
    return {
        "estimate_ms": estimate,
        "upper_ms": upper,
        "tests_with_history": len(known),
        "tests_without_history": len(per_test) - len(known),
        "environment_used": sum(1 for d in known if d[2]),
        "model": {"overhead_ms": model.overhead_ms, "factor": model.factor, "runs": model.runs,
                  "fitted": model.fitted},
    }
