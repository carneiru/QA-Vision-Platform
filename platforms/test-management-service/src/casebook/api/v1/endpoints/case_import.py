"""POST /projects/{id}/cases/import (ADR-023, docs/superpowers/specs/2026-10-06-gherkin-import-design.md)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.casebook.api.deps import ProjectAccess, get_db, require_import_access
from src.casebook.core.config import settings
from src.casebook.gherkin_import.plan import is_mass_archive
from src.casebook.schemas.case_import import ImportRequest, ImportResult
from src.casebook.service import import_service

router = APIRouter()  # mounted at /projects/{project_id}/cases, before cases.router


def _too_large(message: str, setting: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                         detail=f"{message} (the {setting} setting)")


def _check_limits(payload: ImportRequest) -> None:
    if len(payload.files) > settings.IMPORT_MAX_FILES:
        raise _too_large(f"more than {settings.IMPORT_MAX_FILES} files", "IMPORT_MAX_FILES")
    total = 0
    for f in payload.files:
        size = len(f.content.encode("utf-8"))
        if size > settings.IMPORT_MAX_FILE_BYTES:
            raise _too_large(f"{f.path} is over {settings.IMPORT_MAX_FILE_BYTES} bytes", "IMPORT_MAX_FILE_BYTES")
        total += size
    if total > settings.IMPORT_MAX_TOTAL_BYTES:
        raise _too_large(f"files total over {settings.IMPORT_MAX_TOTAL_BYTES} bytes", "IMPORT_MAX_TOTAL_BYTES")


def _out(plan, full: bool) -> dict:
    issue = lambda i: {"path": i.path, "line": i.line, "message": i.message}  # noqa: E731
    summary = plan.summary()
    summary["mass_archive"] = is_mass_archive(summary, full)
    return {
        "plan_hash": plan.plan_hash, "summary": summary,
        "items": [{"action": i.action, "path": i.path, "scenario": i.scenario, "case_number": i.case_number}
                  for i in plan.items],
        "errors": [issue(e) for e in plan.errors], "warnings": [issue(w) for w in plan.warnings],
    }


@router.post("/import", response_model=ImportResult)
def import_cases(
    payload: ImportRequest,
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_import_access),
):
    _check_limits(payload)
    files = [(f.path, f.content) for f in payload.files]
    plan = import_service.plan_import(db, access.project_id, files, payload.full)
    if dry_run:
        return _out(plan, payload.full)
    if payload.expected_plan_hash and payload.expected_plan_hash != plan.plan_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "plan_changed", "message": "Something changed since your preview"})
    summary = plan.summary()
    if is_mass_archive(summary, payload.full) and not payload.allow_mass_archive:
        live = summary["archived"] + summary["unchanged"] + summary["updated"] + summary["moved"]
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "code": "mass_archive", "archived": summary["archived"], "live": live,
            "message": f"This would archive {summary['archived']} of {live} imported cases. "
                       "Check the folder and path prefix, or allow the mass archive to go ahead.",
        })
    try:
        import_service.apply_plan(db, access.project_id, access.user_id, plan)
    except import_service.ImportConflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "import_conflict", "message": "Another import is running; try again"})
    return _out(plan, payload.full)
