from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.ingestion.analytics.trends import RunRow, as_utc, daily, pass_rate, window_start

UTC = ZoneInfo("UTC")
LISBON = ZoneInfo("Europe/Lisbon")
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def row(started, total=1, passed=1, failed=0, errored=0, skipped=0, duration_ms=1000):
    return RunRow(started, total, passed, failed, errored, skipped, duration_ms)


def test_window_start_is_local_midnight():
    assert window_start(NOW, 1, UTC) == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert window_start(NOW, 3, UTC) == datetime(2026, 9, 29, tzinfo=timezone.utc)
    # Lisbon is UTC+1 in summer: local midnight on 1 October is 23:00 UTC on 30 September
    assert window_start(NOW, 1, LISBON) == datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)


def test_a_run_late_in_the_utc_day_lands_on_the_next_local_day():
    late = datetime(2026, 9, 30, 23, 30, tzinfo=timezone.utc)
    assert [(d["date"], d["runs"]) for d in daily([row(late)], NOW, 2, LISBON)] == [("2026-09-30", 0), ("2026-10-01", 1)]
    assert [(d["date"], d["runs"]) for d in daily([row(late)], NOW, 2, UTC)] == [("2026-09-30", 1), ("2026-10-01", 0)]


def test_daylight_saving_change():
    # Lisbon goes back from UTC+1 to UTC at 01:00 UTC on 25 October 2026
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    assert window_start(now, 3, LISBON) == datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)
    before = datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc)  # 00:30 on the 25th in Lisbon (UTC+1)
    after = datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)   # 23:30 on the 25th in Lisbon (UTC)
    days = daily([row(before), row(after)], now, 3, LISBON)
    assert [(d["date"], d["runs"]) for d in days] == [("2026-10-24", 0), ("2026-10-25", 2), ("2026-10-26", 0)]


def test_empty_days_are_zero_filled_oldest_first():
    days = daily([], NOW, 3, UTC)
    assert [d["date"] for d in days] == ["2026-09-29", "2026-09-30", "2026-10-01"]
    assert days[0] == {"date": "2026-09-29", "runs": 0, "total": 0, "passed": 0, "failed": 0, "errored": 0,
                       "skipped": 0, "pass_rate": None, "avg_run_duration_ms": None, "max_run_duration_ms": None}


def test_a_day_adds_up_its_runs():
    days = daily([row(NOW, total=10, passed=6, failed=1, errored=1, skipped=2, duration_ms=1000),
                  row(NOW - timedelta(hours=1), total=2, passed=2, duration_ms=3000)], NOW, 1, UTC)
    assert days == [{"date": "2026-10-01", "runs": 2, "total": 12, "passed": 8, "failed": 1, "errored": 1,
                     "skipped": 2, "pass_rate": 0.8, "avg_run_duration_ms": 2000, "max_run_duration_ms": 3000}]


def test_pass_rate():
    assert pass_rate(6, 10, 2) == 0.75  # errored and failed are not passed; skipped is left out
    assert pass_rate(2, 3, 0) == 0.6667
    assert pass_rate(0, 4, 4) is None
    assert pass_rate(0, 0, 0) is None


def test_runs_outside_the_window_are_ignored():
    assert sum(d["runs"] for d in daily([row(NOW - timedelta(days=5))], NOW, 2, UTC)) == 0


def test_naive_datetimes_are_utc():
    assert as_utc(datetime(2026, 10, 1, 10, 0)) == datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    lisbon_noon = datetime(2026, 10, 1, 12, 0, tzinfo=LISBON)
    assert as_utc(lisbon_noon) == datetime(2026, 10, 1, 11, 0, tzinfo=timezone.utc)
    assert daily([row(datetime(2026, 10, 1, 10, 0))], NOW, 1, UTC)[0]["runs"] == 1


# ---- weekly / monthly buckets ----------------------------------------------------------------

def _row(day_str, passed=1, failed=0, duration=100):
    started = datetime.fromisoformat(day_str + "T12:00:00+00:00")
    total = passed + failed
    return RunRow(started, total, passed, failed, 0, 0, duration)


def test_weekly_buckets_start_on_monday_and_zero_fill():
    from src.ingestion.analytics.trends import bucketed

    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)  # a Friday
    rows = [_row("2026-09-22"), _row("2026-09-30"), _row("2026-10-01", failed=1)]
    out = bucketed(rows, now, 21, ZoneInfo("UTC"), "week")

    dates = [b["date"] for b in out]
    assert dates == ["2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28"]  # Mondays
    assert [b["runs"] for b in out] == [0, 0, 1, 2]
    last = out[-1]
    assert (last["passed"], last["failed"], last["pass_rate"]) == (2, 1, round(2 / 3, 4))


def test_monthly_buckets_group_on_month_start():
    from src.ingestion.analytics.trends import bucketed

    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    rows = [_row("2026-08-20"), _row("2026-09-05"), _row("2026-10-01")]
    out = bucketed(rows, now, 90, ZoneInfo("UTC"), "month")

    assert [b["date"] for b in out] == ["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"]
    assert [b["runs"] for b in out] == [0, 1, 1, 1]


def test_day_bucket_matches_daily():
    from src.ingestion.analytics.trends import bucketed, daily

    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    rows = [_row("2026-10-01"), _row("2026-10-02", failed=1)]
    assert bucketed(rows, now, 7, ZoneInfo("UTC"), "day") == daily(rows, now, 7, ZoneInfo("UTC"))


def test_weekly_respects_the_time_zone():
    from src.ingestion.analytics.trends import bucketed

    # 2026-09-28 00:30 UTC is still Sunday 2026-09-27 in Chicago: previous week's bucket
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    rows = [RunRow(datetime(2026, 9, 28, 0, 30, tzinfo=timezone.utc), 1, 1, 0, 0, 0, 100)]
    out = bucketed(rows, now, 14, ZoneInfo("America/Chicago"), "week")
    by_date = {b["date"]: b["runs"] for b in out}
    assert by_date.get("2026-09-21") == 1  # Chicago-Sunday lands in the Sep 21 week
