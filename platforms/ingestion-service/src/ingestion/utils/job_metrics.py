"""Job heartbeat gauges, read from job_heartbeats on every scrape (monitoring spec 2026-10-10 §3).

    job_last_success_timestamp_seconds{job}   Unix seconds; 0 = no successful pass yet
    job_last_error_timestamp_seconds{job}     Unix seconds; 0 = no failed pass yet

Every job in heartbeat.JOBS is always present (0 without a row), so a job that never succeeded is
stale for the JobStale alert. If the read fails, the job series are left out and
job_heartbeat_read_errors_total goes up: /metrics still answers, so a database blip cannot make
ingestion look down. Prometheus scrapes ingestion with honor_labels: true, so the `job` label here
names the loop job instead of becoming exported_job. The error text is never exposed.
"""
from datetime import datetime, timezone
from typing import Callable, Iterator, Optional

from prometheus_client.core import GaugeMetricFamily
from sqlalchemy.orm import Session

from src.ingestion.jobs.heartbeat import JOBS
from src.ingestion.models.job_heartbeat import JobHeartbeat
from src.ingestion.utils import metrics


def _seconds(moment: Optional[datetime]) -> float:
    if moment is None:
        return 0.0
    if moment.tzinfo is None:  # SQLite hands timezone-aware columns back naive, in UTC
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


class JobHeartbeatCollector:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def describe(self) -> list:
        return []  # registering must not touch the database

    def collect(self) -> Iterator[GaugeMetricFamily]:
        try:
            with self.session_factory() as db:
                rows = {row.job: (row.last_success_at, row.last_error_at) for row in db.query(JobHeartbeat).all()}
        except Exception:
            metrics.HEARTBEAT_READ_ERRORS.inc()
            return
        success = GaugeMetricFamily(
            "job_last_success_timestamp_seconds", "When the job last finished a pass without error (0: never)",
            labels=["job"],
        )
        error = GaugeMetricFamily(
            "job_last_error_timestamp_seconds", "When the job last failed a pass (0: never)", labels=["job"],
        )
        for job in sorted(set(JOBS) | set(rows)):
            last_success, last_error = rows.get(job, (None, None))
            success.add_metric([job], _seconds(last_success))
            error.add_metric([job], _seconds(last_error))
        yield success
        yield error
