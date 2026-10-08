"""Every active case of a project in one compact response, for the report's joins in the dashboard
(docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md, ADR-026). Three queries, no paging."""
from datetime import datetime
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.casebook.models import Case, CaseLabel, Suite, SuiteCase

MAX_CASES = 50_000


class TooManyCases(Exception):
    pass


def folder_of(source_path):
    """The directory part of source_path (the rule of folder_counts); None at the root or for a manual case."""
    if not source_path or "/" not in source_path:
        return None
    return source_path.rsplit("/", 1)[0]


def _index(values) -> Dict[str, int]:
    return {value: i for i, value in enumerate(sorted(values))}


def case_areas(db: Session, project_id: int, now: datetime) -> dict:
    active = (Case.project_id == project_id, Case.status != "archived")
    count = db.execute(select(func.count(Case.id)).where(*active)).scalar_one()
    if count > MAX_CASES:
        raise TooManyCases()
    cases = db.execute(
        select(Case.id, Case.number, Case.title, Case.automated_test_key, Case.source_path, Case.feature_name)
        .where(*active).order_by(Case.number)
    ).all()
    label_rows = db.execute(
        select(CaseLabel.case_id, CaseLabel.label).join(Case, Case.id == CaseLabel.case_id).where(*active)
    ).all()
    suites = db.execute(select(Suite.id, Suite.name).where(Suite.project_id == project_id).order_by(Suite.name)).all()
    member_rows = db.execute(
        select(SuiteCase.case_id, SuiteCase.suite_id).join(Suite, Suite.id == SuiteCase.suite_id)
        .where(Suite.project_id == project_id)
    ).all()

    folders = _index({f for f in (folder_of(c.source_path) for c in cases) if f})
    features = _index({c.feature_name for c in cases if c.feature_name})
    labels = _index({label for _, label in label_rows})
    suite_index = {suite_id: i for i, (suite_id, _) in enumerate(suites)}
    labels_of: Dict[int, List[int]] = {}
    for case_id, label in label_rows:
        labels_of.setdefault(case_id, []).append(labels[label])
    suites_of: Dict[int, List[int]] = {}
    for case_id, suite_id in member_rows:
        suites_of.setdefault(case_id, []).append(suite_index[suite_id])

    linked = sum(1 for c in cases if c.automated_test_key)
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {"cases": len(cases), "linked": linked, "manual": len(cases) - linked},
        "folders": sorted(folders, key=folders.get),
        "features": sorted(features, key=features.get),
        "labels": sorted(labels, key=labels.get),
        "suites": [{"id": suite_id, "name": name} for suite_id, name in suites],
        "cases": [
            {"n": c.number, "t": c.title, "k": c.automated_test_key.lower() if c.automated_test_key else None,
             "fo": folders.get(folder_of(c.source_path)) if folder_of(c.source_path) else None,
             "fe": features[c.feature_name] if c.feature_name else None,
             "l": sorted(labels_of.get(c.id, [])), "s": sorted(suites_of.get(c.id, []))}
            for c in cases
        ],
    }
