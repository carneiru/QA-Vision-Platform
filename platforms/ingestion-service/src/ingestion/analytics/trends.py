"""Daily trend arithmetic over run rows. Pure: no database, no clock."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class RunRow:
    started_at: datetime
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    duration_ms: int


def as_utc(value: datetime) -> datetime:
    """SQLite (the tests) hands back naive datetimes; they were stored as UTC."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def pass_rate(passed: int, total: int, skipped: int) -> Optional[float]:
    considered = total - skipped
    return None if considered <= 0 else round(passed / considered, 4)


def window_start(now: datetime, days: int, zone: ZoneInfo) -> datetime:
    """Local midnight `days - 1` days before today in `zone`, as an aware UTC datetime."""
    first = as_utc(now).astimezone(zone).date() - timedelta(days=days - 1)
    return datetime.combine(first, time.min, tzinfo=zone).astimezone(timezone.utc)


def daily(rows: Iterable[RunRow], now: datetime, days: int, zone: ZoneInfo) -> List[dict]:
    today = as_utc(now).astimezone(zone).date()
    dates = [today - timedelta(days=days - 1 - offset) for offset in range(days)]
    buckets: Dict[date, List[RunRow]] = defaultdict(list)
    wanted = set(dates)
    for run in rows:
        local_day = as_utc(run.started_at).astimezone(zone).date()
        if local_day in wanted:
            buckets[local_day].append(run)
    return [_day(day, buckets.get(day, [])) for day in dates]


def _day(day: date, runs: List[RunRow]) -> dict:
    total = sum(r.total for r in runs)
    skipped = sum(r.skipped for r in runs)
    passed = sum(r.passed for r in runs)
    durations = [r.duration_ms for r in runs]
    return {
        "date": day.isoformat(),
        "runs": len(runs),
        "total": total,
        "passed": passed,
        "failed": sum(r.failed for r in runs),
        "errored": sum(r.errored for r in runs),
        "skipped": skipped,
        "pass_rate": pass_rate(passed, total, skipped),
        "avg_run_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "max_run_duration_ms": max(durations) if durations else None,
    }


BUCKETS = ("day", "week", "month")


def _bucket_start(day: date, bucket: str) -> date:
    if bucket == "week":
        return day - timedelta(days=day.weekday())  # Monday
    if bucket == "month":
        return day.replace(day=1)
    return day


def _next_bucket(start: date, bucket: str) -> date:
    if bucket == "week":
        return start + timedelta(days=7)
    if bucket == "month":
        return (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start + timedelta(days=1)


def bucketed(rows: Iterable[RunRow], now: datetime, days: int, zone: ZoneInfo, bucket: str) -> List[dict]:
    """daily(), but grouped into week (Monday-start) or month buckets on the
    local calendar. Every bucket touching the window appears, zero-filled; the
    first and last may be partial. `date` is the bucket's start day."""
    if bucket == "day":
        return daily(rows, now, days, zone)
    today = as_utc(now).astimezone(zone).date()
    first_day = today - timedelta(days=days - 1)
    wanted = {first_day + timedelta(days=offset) for offset in range(days)}

    starts = []
    cursor = _bucket_start(first_day, bucket)
    while cursor <= today:
        starts.append(cursor)
        cursor = _next_bucket(cursor, bucket)

    grouped: Dict[date, List[RunRow]] = defaultdict(list)
    for run in rows:
        local_day = as_utc(run.started_at).astimezone(zone).date()
        if local_day in wanted:
            grouped[_bucket_start(local_day, bucket)].append(run)
    return [_day(start, grouped.get(start, [])) for start in starts]
