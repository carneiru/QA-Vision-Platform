"""Features: the cases grouped by the .feature file they came from, and one file's raw text."""
import re
from collections import defaultdict
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.casebook.models import Case, FeatureFile
from src.casebook.service.case_service import case_key, filtered_cases

CASE_NUMBERS_SHOWN = 200


def folder_of(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    return path.rsplit("/", 1)[0] if "/" in path else ""


def list_features(db: Session, project_id: int, *, limit: int, offset: int, **filters) -> dict:
    """One row per (feature name, path) over the active cases the filters keep; the manual cases form one
    last row. Ordered by folder, then feature name. Groups are counted and sorted here: a project has
    a few thousand files at most, and the folder is not a column."""
    query, _ = filtered_cases(db, project_id, **filters)
    query = query.filter(Case.status != "archived")
    sub = query.with_entities(Case.id, Case.feature_name, Case.source_path).subquery()
    groups = db.query(sub.c.feature_name, sub.c.source_path, func.count(sub.c.id)).group_by(
        sub.c.feature_name, sub.c.source_path).all()
    groups.sort(key=lambda g: (g[1] is None, folder_of(g[1]) or "", (g[0] or "").casefold(), g[1] or ""))
    page = groups[offset:offset + limit]
    numbers = defaultdict(list)
    if page:
        wanted = or_(*[and_(Case.feature_name == name if name is not None else Case.feature_name.is_(None),
                            Case.source_path == path if path is not None else Case.source_path.is_(None))
                       for name, path, _ in page])
        rows = query.filter(wanted).order_by(Case.number).with_entities(
            Case.number, Case.feature_name, Case.source_path).all()
        for number, name, path in rows:
            numbers[(name, path)].append(number)
    stored = set()
    paths = [p for _, p, _ in page if p is not None]
    if paths:
        stored = {p for (p,) in db.query(FeatureFile.path).filter(
            FeatureFile.project_id == project_id, FeatureFile.path.in_(paths)).all()}
    items = [{"feature_name": name, "path": path, "folder": folder_of(path), "case_count": count,
              "case_numbers": numbers[(name, path)][:CASE_NUMBERS_SHOWN], "has_source": path in stored}
             for name, path, count in page]
    return {"total": len(groups), "items": items}


def scenario_lines(content: str, feature_name: Optional[str], names: list) -> dict:
    """name -> 1-based line of the scenario's heading in the raw file. Any keyword and language: a line
    that is `<words>: <name>`. The first such line is the Feature's own when the names are equal."""
    lines = content.lstrip("﻿").splitlines()
    found = {}
    for name in set(names):
        pattern = re.compile(r"^\s*[^:#@|\s][^:#@|]*:\s*" + re.escape(name) + r"\s*$")
        hits = [i + 1 for i, text in enumerate(lines) if pattern.match(text)]
        if name == feature_name:
            hits = hits[1:]
        if hits:
            found[name] = hits[0]
    return found


def feature_detail(db: Session, project_id: int, path: str) -> Optional[dict]:
    """None when no active case has this path (an archived or removed file is gone)."""
    cases = (db.query(Case).filter(Case.project_id == project_id, Case.source_path == path,
                                   Case.status != "archived").order_by(Case.number).all())
    if not cases:
        return None
    file: Optional[FeatureFile] = db.query(FeatureFile).filter(
        FeatureFile.project_id == project_id, FeatureFile.path == path).one_or_none()
    feature_name = cases[0].feature_name or (file.feature_name if file else None)
    lines = scenario_lines(file.content, feature_name, [c.scenario_name for c in cases if c.scenario_name]) if file else {}
    # File order when the raw text is stored and the heading is found, else by number (creation order)
    cases.sort(key=lambda c: (c.scenario_name not in lines, lines.get(c.scenario_name, 0), c.number))
    return {
        "feature_name": feature_name, "path": path,
        "folder": folder_of(path), "content": file.content if file else None,
        "imported_at": file.imported_at if file else None,
        "cases": [{"number": c.number, "key": case_key(c.number), "title": c.title,
                   "scenario_name": c.scenario_name, "status": c.status, "priority": c.priority,
                   "automated_test_key": c.automated_test_key, "line": lines.get(c.scenario_name)} for c in cases],
    }
