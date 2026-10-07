"""Play: a run request dispatches the project's CI workflow; GETs refresh it from GitHub (no worker)."""
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.casebook.models import Case, CiTarget, RunRequest, Suite, SuiteCase
from src.casebook.models.ci import ACTIVE_STATUSES
from src.casebook.service.case_service import case_key
from src.casebook.utils import github_client, secret_box

THROTTLE = timedelta(seconds=5)
START_TIMEOUT = timedelta(minutes=2)
MATCH_WINDOW = timedelta(minutes=1)
MAX_CASES = 200
MAX_INPUT_CHARS = 65000  # GitHub refuses workflow_dispatch inputs over 65 535 characters in total
NOT_STARTED = "The workflow did not start"
RUN_GONE = "The run is no longer on GitHub"
QUEUED_ON_GITHUB = ("queued", "waiting", "requested", "pending")
RUN_URL_PREFIX = "https://github.com/"


class NoTarget(Exception):
    """The project has no CI target."""


class BadSelection(Exception):
    """The selection cannot run; the message names the case numbers."""


class SuiteNotFound(Exception):
    pass


class RunActive(Exception):
    def __init__(self, request_id: Optional[int]):
        super().__init__("A run is in progress")
        self.request_id = request_id


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(moment: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands DateTime(timezone=True) back naive; every time stored here is UTC."""
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=timezone.utc)


def run_title(request_id: int) -> str:
    return f"QA Vision #{request_id}"


def _keys(numbers: List[int]) -> str:
    return ", ".join(case_key(n) for n in numbers)


def _numbers(db: Session, project_id: int, case_numbers: Optional[List[int]], suite_id: Optional[int]) -> List[int]:
    if suite_id is None:
        return list(dict.fromkeys(case_numbers or []))
    suite = db.query(Suite).filter(Suite.project_id == project_id, Suite.id == suite_id).one_or_none()
    if suite is None:
        raise SuiteNotFound()
    rows = (db.query(Case.number).join(SuiteCase, SuiteCase.case_id == Case.id)
            .filter(SuiteCase.suite_id == suite.id).order_by(SuiteCase.position).all())
    return [r.number for r in rows]


def build_selection(db: Session, project_id: int, case_numbers: Optional[List[int]],
                    suite_id: Optional[int]) -> List[dict]:
    numbers = _numbers(db, project_id, case_numbers, suite_id)
    if not numbers:
        raise BadSelection("Nothing to run: the suite has no cases")
    if len(numbers) > MAX_CASES:
        raise BadSelection(f"At most {MAX_CASES} cases per run; this selection has {len(numbers)}")
    found = {c.number: c for c in db.query(Case).filter(Case.project_id == project_id, Case.number.in_(numbers))}
    unknown = [n for n in numbers if n not in found]
    manual = [n for n in numbers if n in found and not found[n].source_path]
    archived = [n for n in numbers if n in found and found[n].source_path and found[n].status == "archived"]
    unnamed = [n for n in numbers if n in found and found[n].source_path and found[n].status != "archived"
               and not found[n].scenario_name]
    problems = []
    if unknown:
        problems.append(f"No such case: {_keys(unknown)}")
    if manual:
        problems.append(f"Manual cases cannot run: {_keys(manual)}")
    if archived:
        problems.append(f"Archived cases cannot run: {_keys(archived)}")
    if unnamed:
        problems.append(f"{_keys(unnamed)}: re-import the .feature files first")
    if problems:
        raise BadSelection(". ".join(problems))
    return [{"case_number": n, "path": found[n].source_path, "name": found[n].scenario_name} for n in numbers]


def dispatch_inputs(request_id: int, selection: List[dict]) -> dict:
    """paths: a JSON array of the files, once each (a path may contain a space); names: a JSON array of
    the raw scenario names; request_id: the row id, which the workflow puts in its run-name."""
    paths = list(dict.fromkeys(item["path"] for item in selection))
    return {"paths": json.dumps(paths, ensure_ascii=False),
            "names": json.dumps([item["name"] for item in selection], ensure_ascii=False),
            "request_id": str(request_id)}


def _target_and_token(db: Session, project_id: int) -> Tuple[CiTarget, str]:
    target = db.get(CiTarget, project_id)
    if target is None:
        raise NoTarget()
    return target, secret_box.decrypt(target.token_encrypted)


def active_request(db: Session, project_id: int) -> Optional[RunRequest]:
    return db.query(RunRequest).filter(
        RunRequest.project_id == project_id, RunRequest.status.in_(ACTIVE_STATUSES)).one_or_none()


def needs_refresh(row: RunRequest, at: datetime) -> bool:
    return row.status in ACTIVE_STATUSES


def _claimed(db: Session, project_id: int, own_id: int) -> frozenset:
    rows = db.query(RunRequest.github_run_id).filter(
        RunRequest.project_id == project_id, RunRequest.id != own_id, RunRequest.github_run_id.isnot(None)).all()
    return frozenset(r[0] for r in rows)


def safe_run_url(url: Optional[str]) -> Optional[str]:
    """Only a github.com page is stored, so the dashboard never renders an untrusted link."""
    return url if isinstance(url, str) and url.startswith(RUN_URL_PREFIX) else None


def _match(db: Session, row: RunRequest, target: CiTarget, token: str) -> Optional[dict]:
    """The 204 fallback only: GitHub gave no run details at dispatch, so find the run by its title."""
    run = github_client.find_run(token, target.repo, target.workflow, run_title(row.id),
                                 aware(row.requested_at) - MATCH_WINDOW, _claimed(db, row.project_id, row.id))
    if run is not None:
        row.github_run_id = int(run["id"])
        row.github_run_url = safe_run_url(run.get("html_url"))
    return run


def _map_status(row: RunRequest, run: dict) -> None:
    status, conclusion = run.get("status"), run.get("conclusion")
    if status == "completed":
        row.conclusion = str(conclusion)[:30] if conclusion else None
        row.status = "cancelled" if conclusion == "cancelled" else "completed"
    elif row.status == "cancelling":
        return  # stays cancelling until GitHub reports the run completed
    elif status == "in_progress":
        row.status = "running"
    elif status in QUEUED_ON_GITHUB:
        row.status = "queued"


def _apply_github(db: Session, row: RunRequest, target: CiTarget, token: str, at: datetime) -> None:
    if row.github_run_id is None:
        run = _match(db, row, target, token)
        if run is None:
            if at - aware(row.requested_at) >= START_TIMEOUT:
                row.status, row.error = "failed_to_start", NOT_STARTED
            return
    else:
        try:
            run = github_client.get_run(token, target.repo, row.github_run_id)
        except github_client.RateLimited:
            raise
        except github_client.GitHubError as exc:
            if exc.status == 404:  # the run (or its repository) is gone: nothing left to wait for
                row.status, row.error = "cancelled", RUN_GONE
                return
            raise
        row.error = None
    _map_status(row, run)


def refresh(db: Session, row: RunRequest, force: bool = False) -> RunRequest:
    """Bring a request up to date with GitHub, at most every 5 s unless forced. A GitHub failure (rate
    limit, outage) or an unreadable token leaves the state as it was; checked_at still moves, so a failing
    GitHub is not asked on every GET."""
    at = now()
    if not needs_refresh(row, at):
        return row
    checked = aware(row.checked_at)
    if not force and checked is not None and at - checked < THROTTLE:
        return row
    target = db.get(CiTarget, row.project_id)
    if target is None:
        return row
    try:
        _apply_github(db, row, target, secret_box.decrypt(target.token_encrypted), at)
    except (github_client.GitHubError, secret_box.SecretsUnavailable) as exc:
        db.rollback()
        # A known run we cannot read (token revoked, GitHub down): keep its status, say why it is stale
        if (isinstance(exc, github_client.GitHubError) and not isinstance(exc, github_client.RateLimited)
                and row.github_run_id is not None):
            row.error = exc.message[:500]
    row.checked_at = at
    db.commit()
    return row


def create(db: Session, project_id: int, user_id: int, case_numbers: Optional[List[int]],
           suite_id: Optional[int]) -> RunRequest:
    target, token = _target_and_token(db, project_id)
    selection = build_selection(db, project_id, case_numbers, suite_id)
    preview = dispatch_inputs(0, selection)
    if len(preview["paths"]) + len(preview["names"]) + 20 > MAX_INPUT_CHARS:
        raise BadSelection("This selection is too large for one GitHub dispatch: select fewer cases")
    active = active_request(db, project_id)
    if active is not None:
        refresh(db, active, force=True)  # a run that ended while nobody looked must not block Play
        if active.status in ACTIVE_STATUSES:
            raise RunActive(active.id)
    row = RunRequest(project_id=project_id, requested_by=user_id, requested_at=now(), selection=selection,
                     suite_id=suite_id, status="queued")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RunActive(None)  # another Play committed first (the partial unique index)
    db.refresh(row)
    try:
        started = github_client.dispatch(token, target.repo, target.workflow, target.ref,
                                         dispatch_inputs(row.id, selection))
    except github_client.RateLimited:
        db.delete(row)
        db.commit()
        raise
    except github_client.GitHubError as exc:
        row.status, row.error = "failed_to_start", exc.message[:500]
        db.commit()
        return row
    if started is not None:  # 200 with run details: Stop and polling work on this run at once
        row.github_run_id = started.run_id
        row.github_run_url = safe_run_url(started.html_url)
        db.commit()
    # On None (a 204), the row keeps no run id: polling matches it by title (the fallback)
    return row


def list_requests(db: Session, project_id: int, limit: int, offset: int) -> Tuple[int, List[RunRequest]]:
    query = db.query(RunRequest).filter(RunRequest.project_id == project_id)
    total = query.count()
    rows = query.order_by(RunRequest.requested_at.desc(), RunRequest.id.desc()).offset(offset).limit(limit).all()
    for row in rows:
        refresh(db, row)
    return total, rows


def get_request(db: Session, project_id: int, request_id: int) -> Optional[RunRequest]:
    row = db.query(RunRequest).filter(RunRequest.project_id == project_id, RunRequest.id == request_id).one_or_none()
    return refresh(db, row) if row is not None else None


def out(row: RunRequest) -> dict:
    selection = row.selection or []
    return {
        "id": row.id, "requested_by": row.requested_by, "requested_at": aware(row.requested_at),
        "selection": selection, "case_count": len(selection), "suite_id": row.suite_id, "status": row.status,
        "conclusion": row.conclusion, "github_run_id": row.github_run_id, "github_run_url": row.github_run_url,
        "stopped_by": row.stopped_by, "stopped_at": aware(row.stopped_at), "error": row.error,
        "checked_at": aware(row.checked_at), "refreshing": needs_refresh(row, now()),
    }
