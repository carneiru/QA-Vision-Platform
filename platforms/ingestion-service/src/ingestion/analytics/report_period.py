"""Report periods and buckets on the user's local calendar. Pure: no database, no clock.

The period is the days the user picked, from local midnight of `first` to local midnight after
`last` (end exclusive). The previous period is the same number of days just before it.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from src.ingestion.analytics.trends import as_utc

MAX_SPAN_DAYS = 90
MAX_AGE_DAYS = 400
AUTO_DAY_LIMIT = 31


class PeriodError(ValueError):
    """A period the report refuses; the message names the rule and is the 422 detail."""


def local_midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return as_utc(moment).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_day(moment: datetime, zone: ZoneInfo) -> date:
    return as_utc(moment).astimezone(zone).date()


@dataclass(frozen=True)
class Period:
    first: date
    last: date
    zone: ZoneInfo

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    @property
    def start(self) -> datetime:
        return local_midnight(self.first, self.zone)

    @property
    def end(self) -> datetime:
        return local_midnight(self.last + timedelta(days=1), self.zone)

    def previous(self) -> "Period":
        return Period(self.first - timedelta(days=self.days), self.first - timedelta(days=1), self.zone)

    def out(self) -> dict:
        return {"from": self.first.isoformat(), "to": self.last.isoformat(), "days": self.days,
                "start": iso(self.start), "end": iso(self.end)}


def check_period(first: date, last: date, zone: ZoneInfo, now: datetime) -> Period:
    if first > last:
        raise PeriodError("from must be on or before to")
    span = (last - first).days + 1
    if span > MAX_SPAN_DAYS:
        raise PeriodError(f"The period is {span} days; it can be at most {MAX_SPAN_DAYS}")
    today = local_day(now, zone)
    if last > today + timedelta(days=1):
        raise PeriodError("to is in the future")
    if first < today - timedelta(days=MAX_AGE_DAYS):
        raise PeriodError(f"from is more than {MAX_AGE_DAYS} days ago")
    return Period(first, last, zone)


def choose_bucket(requested: str, days: int) -> str:
    if requested != "auto":
        return requested
    return "day" if days <= AUTO_DAY_LIMIT else "week"


def bucket_starts(period: Period, bucket: str) -> List[date]:
    """Every bucket touching the period, oldest first; a week starts on Monday, so the first and
    last weeks may be partial."""
    if bucket == "day":
        return [period.first + timedelta(days=i) for i in range(period.days)]
    cursor = period.first - timedelta(days=period.first.weekday())
    starts = []
    while cursor <= period.last:
        starts.append(cursor)
        cursor += timedelta(days=7)
    return starts


def bucket_index(day: date, starts: List[date], bucket: str) -> Optional[int]:
    if not starts:
        return None
    offset = (day - starts[0]).days
    index = offset if bucket == "day" else offset // 7
    return index if 0 <= index < len(starts) and offset >= 0 else None
