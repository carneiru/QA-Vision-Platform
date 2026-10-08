"""Queries behind POST /analytics/report (docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md).

One scoped-runs query over the previous period plus the period feeds every section. Counting stays in
SQL; sequences, streaks and signatures are computed in Python over the rows (src/ingestion/analytics).
The handler never writes."""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence

from sqlalchemy import Integer, String, and_, any_, bindparam, false, func, not_, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.ingestion.analytics.report_period import Period, bucket_starts, iso
from src.ingestion.analytics.trends import as_utc
from src.ingestion.models import Run, RunResult

STATEMENT_TIMEOUT = "20s"  # below the gateway's 30 s proxy_read_timeout
REPORT_TIMEOUT_MESSAGE = "This report took too long. Narrow the period or the filters."
QUERY_CANCELED = "57014"


@dataclass(frozen=True)
class Scope:
    project_id: int
    period: Period
    previous: Period
    branch: Optional[str]
    environment: Optional[str]
    ci_provider: Optional[str]
    origin: str                       # any | ci | qeos
    urls: tuple                       # lower-cased Play run URLs (origin != any)
    keys: Optional[tuple]             # lower-cased, de-duplicated test keys, or None

    @classmethod
    def from_request(cls, project_id: int, body, period: Period) -> "Scope":
        keys = None if body.test_keys is None else tuple(sorted({k.lower() for k in body.test_keys}))
        urls = tuple(sorted({u.lower() for u in (body.requested_run_urls or [])}))
        return cls(project_id=project_id, period=period, previous=period.previous(),
                   branch=body.branch or None, environment=body.environment or None,
                   ci_provider=body.ci_provider or None, origin=body.origin, urls=urls, keys=keys)


@dataclass(frozen=True)
class ScopedRun:
    id: int
    started_at: datetime
    branch: Optional[str]
    duration_ms: int
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    current: bool  # in the period; False: in the previous period


def in_list(db: Session, column, values: Sequence, item_type=String):
    """`column IN values`. PostgreSQL gets one array parameter (`= ANY(:x)`), so 20,000 keys stay one
    bind; SQLite (the tests) gets an expanding IN."""
    values = list(values)
    if db.get_bind().dialect.name == "postgresql":
        return column == any_(bindparam(None, values, type_=ARRAY(item_type)))
    return column.in_(values)


def run_filters(db: Session, scope: Scope) -> list:
    """Project and window, then branch, environment, CI provider and origin. These are checked on the
    window's few thousand runs, so they need no index."""
    filters = [Run.project_id == scope.project_id, Run.started_at >= scope.previous.start,
               Run.started_at < scope.period.end]
    if scope.branch:
        filters.append(Run.branch == scope.branch)
    if scope.environment:
        filters.append(Run.environment == scope.environment)
    if scope.ci_provider:
        filters.append(Run.ci_provider == scope.ci_provider)
    if scope.origin == "qeos":
        filters.append(requested_from_qeos(db, scope))
    elif scope.origin == "ci":
        if scope.urls:  # no Play URLs: every run is CI
            filters.append(not_(requested_from_qeos(db, scope)))
    return filters


def requested_from_qeos(db: Session, scope: Scope):
    """A GitHub Actions run whose URL is one of a Play's github_run_url (ADR-026). The match is on the
    lower-cased URL; a trailing slash makes it another URL. Never sends an empty list to in_list."""
    if not scope.urls:
        return false()
    # A NULL URL makes the AND false, never NULL, so not_() of it keeps the run.
    return and_(Run.ci_provider == "github_actions", Run.ci_run_url.is_not(None),
                in_list(db, func.lower(Run.ci_run_url), scope.urls))


def key_filter(db: Session, scope: Scope) -> list:
    """The test_keys restriction for any query over test_results ([] without keys)."""
    return [] if scope.keys is None else [in_list(db, RunResult.test_key, scope.keys)]


def scoped_runs(db: Session, scope: Scope) -> List[ScopedRun]:
    rows = db.execute(
        select(Run.id, Run.started_at, Run.branch, Run.duration_ms, Run.total, Run.passed, Run.failed,
               Run.errored, Run.skipped)
        .where(*run_filters(db, scope))
        .order_by(Run.started_at, Run.id)
    ).all()
    start = scope.period.start
    return [ScopedRun(r.id, as_utc(r.started_at), r.branch, r.duration_ms, r.total, r.passed, r.failed,
                      r.errored, r.skipped, as_utc(r.started_at) >= start) for r in rows]


def runs_with_results(db: Session, scope: Scope, runs: List[ScopedRun]) -> set:
    """Ids of the runs that count: every scoped run, or with test_keys the runs that have at least one
    result for those keys."""
    if scope.keys is None or not runs:
        return {r.id for r in runs}
    rows = db.execute(
        select(RunResult.run_id).distinct()
        .where(in_list(db, RunResult.run_id, [r.id for r in runs], Integer), *key_filter(db, scope))
    ).all()
    return {run_id for (run_id,) in rows}


# Section name -> builder(db, scope, runs, context) -> dict. Tasks 4, 17, 19, 24, 25 register theirs.
SECTION_BUILDERS: Dict[str, Callable] = {}


@dataclass(frozen=True)
class Context:
    """What every section shares: the bucket and its starts, and the runs that count."""
    bucket: str
    starts: list
    counted: set


def build_report(db: Session, scope: Scope, sections: List[str], bucket: str, now: datetime) -> dict:
    runs = scoped_runs(db, scope)
    counted = runs_with_results(db, scope, runs)
    context = Context(bucket=bucket, starts=bucket_starts(scope.period, bucket), counted=counted)
    out = {
        "period": scope.period.out(),
        "previous_period": scope.previous.out(),
        "tz": scope.period.zone.key,
        "bucket": bucket,
        "generated_at": iso(now),
        "scope": {
            "runs": sum(1 for r in runs if r.current and r.id in counted),
            "previous_runs": sum(1 for r in runs if not r.current and r.id in counted),
            "test_keys": None if scope.keys is None else len(scope.keys),
        },
    }
    for name in sections:
        builder = SECTION_BUILDERS.get(name)
        out[name] = builder(db, scope, runs, context) if builder else None
    return out


def limit_statement_time(db: Session) -> None:
    """Every report query in this transaction is cancelled after 20 s (PostgreSQL only)."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))


def is_timeout(exc: OperationalError) -> bool:
    orig = getattr(exc, "orig", None)
    return (getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)) == QUERY_CANCELED
