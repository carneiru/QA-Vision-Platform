"""Queries behind POST /analytics/report (docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md).

One scoped-runs query over the previous period plus the period feeds every section. Counting stays in
SQL; sequences, streaks and signatures are computed in Python over the rows (src/ingestion/analytics).
The handler never writes."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Sequence

from sqlalchemy import Integer, String, and_, any_, bindparam, case, distinct, false, func, not_, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.ingestion.analytics.report_causes import Occurrence, group_causes
from src.ingestion.analytics.report_period import Period, bucket_index, bucket_starts, iso, local_day
from src.ingestion.analytics.signature import headline, signature
from src.ingestion.analytics.trends import as_utc, pass_rate
from src.ingestion.models import Run, RunResult
from src.ingestion.service.analytics_service import muted_keys

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


FAILING = ("failed", "errored")
TOP = 10
MAX_FACETS = 50


@dataclass
class Counts:
    executions: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    duration_ms: int = 0  # sum of result durations; only filled when test_keys are set

    def add(self, other: "Counts") -> None:
        self.executions += other.executions
        self.passed += other.passed
        self.failed += other.failed
        self.errored += other.errored
        self.skipped += other.skipped
        self.duration_ms += other.duration_ms

    def out(self) -> dict:
        return {"executions": self.executions, "passed": self.passed, "failed": self.failed,
                "errored": self.errored, "skipped": self.skipped,
                "pass_rate": pass_rate(self.passed, self.executions, self.skipped)}


def _count(*statuses: str):
    return func.sum(case((RunResult.status.in_(statuses), 1), else_=0))


def run_counts(db: Session, scope: Scope, runs: List[ScopedRun]) -> Dict[int, Counts]:
    """Per counted run. Without test_keys the run's own counters (computed from its results at upload);
    with test_keys the results for those keys, which also gives the summed test time."""
    if scope.keys is None:
        return {r.id: Counts(r.total, r.passed, r.failed, r.errored, r.skipped) for r in runs}
    if not runs:
        return {}
    rows = db.execute(
        select(RunResult.run_id, func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"),
               _count("skipped"), func.sum(RunResult.duration_ms))
        .where(in_list(db, RunResult.run_id, [r.id for r in runs], Integer), *key_filter(db, scope))
        .group_by(RunResult.run_id)
    ).all()
    return {run_id: Counts(n, int(p or 0), int(f or 0), int(e or 0), int(s or 0), int(d or 0))
            for run_id, n, p, f, e, s, d in rows}


def _test_figures(db: Session, scope: Scope, ids: list) -> tuple:
    """(distinct tests executed, distinct tests with a failing execution) over the given runs."""
    if not ids:
        return 0, 0
    tests, failing = db.execute(
        select(func.count(distinct(RunResult.test_key)),
               func.count(distinct(case((RunResult.status.in_(FAILING), RunResult.test_key)))))
        .where(in_list(db, RunResult.run_id, ids, Integer), *key_filter(db, scope))
    ).one()
    return int(tests or 0), int(failing or 0)


def _totals(db: Session, scope: Scope, runs: List[ScopedRun], counts: Dict[int, Counts]) -> dict:
    total = Counts()
    for r in runs:
        total.add(counts[r.id])
    tests, failing = _test_figures(db, scope, [r.id for r in runs])
    durations = [r.duration_ms for r in runs]
    return {"runs": len(runs), **total.out(), "tests": tests, "failing_tests": failing,
            "avg_run_duration_ms": round(sum(durations) / len(durations)) if durations else None}


def _bucket_rows(scope: Scope, context: Context, runs, counts, shift_days: int) -> List[dict]:
    """One entry per bucket of the period. shift_days moves a previous-period run onto the bucket that
    lies `days` later, so the previous period lines up bucket by bucket (Ruling 2)."""
    per = [Counts() for _ in context.starts]
    per_runs = [0] * len(context.starts)
    zone = scope.period.zone
    for r in runs:
        index = bucket_index(local_day(r.started_at, zone) + timedelta(days=shift_days), context.starts, context.bucket)
        if index is None:
            continue
        per[index].add(counts[r.id])
        per_runs[index] += 1
    return [{"date": (start - timedelta(days=shift_days)).isoformat(), "runs": per_runs[i], **per[i].out()}
            for i, start in enumerate(context.starts)]


def _test_rows(db: Session, scope: Scope, ids: list, *, slowest: bool) -> List[dict]:
    """The 10 most failing (only tests with a failure) or slowest tests, ordered as /tests orders them."""
    if not ids:
        return []
    failures = _count(*FAILING)
    average = func.avg(RunResult.duration_ms)
    query = (
        select(RunResult.test_key, func.max(RunResult.suite), func.max(RunResult.class_name),
               func.max(RunResult.name), func.count(RunResult.id), failures, _count("passed"), _count("skipped"),
               average)
        .where(in_list(db, RunResult.run_id, ids, Integer), *key_filter(db, scope))
        .group_by(RunResult.test_key)
    )
    query = query.order_by(average.desc(), RunResult.test_key) if slowest else \
        query.having(failures > 0).order_by(failures.desc(), RunResult.test_key)
    out = []
    for key, suite, class_name, name, n, failed, passed, skipped, avg in db.execute(query.limit(TOP)).all():
        row = {"test_key": key, "suite": suite, "class_name": class_name, "name": name, "executions": n}
        if slowest:
            row["avg_duration_ms"] = round(float(avg)) if avg is not None else None
        else:
            row["failures"] = int(failed)
            row["pass_rate"] = pass_rate(int(passed), n, int(skipped))
        out.append(row)
    return out


def _branches(runs: List[ScopedRun], counts: Dict[int, Counts]) -> List[dict]:
    grouped: Dict[Optional[str], list] = {}
    for r in runs:
        grouped.setdefault(r.branch, []).append(r)
    rows = []
    for branch, members in grouped.items():
        total = Counts()
        for r in members:
            total.add(counts[r.id])
        rows.append({"branch": branch, "runs": len(members), "executions": total.executions,
                     "failures": total.failed + total.errored,
                     "pass_rate": pass_rate(total.passed, total.executions, total.skipped)})
    rows.sort(key=lambda b: (-b["runs"], b["branch"] is None, b["branch"] or ""))
    return rows[:TOP]


def _facets(db: Session, scope: Scope) -> dict:
    """The period's busiest values, ignoring every other filter, so they offer a way out of an empty result."""
    out = {}
    for name, column in (("branches", Run.branch), ("environments", Run.environment), ("ci_providers", Run.ci_provider)):
        rows = db.execute(
            select(column, func.count(Run.id))
            .where(Run.project_id == scope.project_id, Run.started_at >= scope.period.start,
                   Run.started_at < scope.period.end, column.is_not(None))
            .group_by(column).order_by(func.count(Run.id).desc(), column).limit(MAX_FACETS)
        ).all()
        out[name] = [value for value, _ in rows]
    return out


def summary(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    counted = [r for r in runs if r.id in context.counted]
    counts = run_counts(db, scope, counted)
    current = [r for r in counted if r.current]
    previous = [r for r in counted if not r.current]
    current_ids = [r.id for r in current]
    return {
        "current": _totals(db, scope, current, counts),
        "previous": _totals(db, scope, previous, counts) if previous else None,
        "buckets": _bucket_rows(scope, context, current, counts, 0),
        "previous_buckets": _bucket_rows(scope, context, previous, counts, scope.period.days),
        "top_failing": _test_rows(db, scope, current_ids, slowest=False),
        "slowest": _test_rows(db, scope, current_ids, slowest=True),
        "branches": _branches(current, counts),
        "facets": _facets(db, scope),
    }


SECTION_BUILDERS["summary"] = summary


MESSAGE_PREFIX = 2000  # only the first line names a cause; this bounds memory on long stack traces


def _bucket_of(scope: Scope, context: Context, run: ScopedRun) -> Optional[int]:
    if not run.current:
        return None
    return bucket_index(local_day(run.started_at, scope.period.zone), context.starts, context.bucket)


def failure_causes(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    """The failing rows of the in-scope runs of both periods (through ix_test_results_failing), grouped by
    signature in Python, as the run view does."""
    by_id = {r.id: r for r in runs if r.id in context.counted}
    if not by_id:
        return group_causes([], len(context.starts))
    rows = db.execute(
        select(RunResult.run_id, RunResult.test_key, RunResult.suite, RunResult.class_name, RunResult.name,
               RunResult.status, func.substr(RunResult.message, 1, MESSAGE_PREFIX))
        .where(in_list(db, RunResult.run_id, list(by_id), Integer), RunResult.status.in_(FAILING),
               *key_filter(db, scope))
    ).all()
    muted = {key.lower() for key in muted_keys(db, scope.project_id)}
    occurrences = []
    for run_id, key, suite, class_name, name, status, message in rows:
        run = by_id[run_id]
        occurrences.append(Occurrence(signature(message), headline(message), key, suite, class_name, name, status,
                                      run_id, run.started_at, run.current, key.lower() in muted,
                                      _bucket_of(scope, context, run)))
    return group_causes(occurrences, len(context.starts))


SECTION_BUILDERS["failure_causes"] = failure_causes
