"""Features: the cases grouped by the .feature file they came from, and one file's raw text."""
import re
from collections import defaultdict
from typing import Optional

from gherkin.dialect import DIALECTS
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from src.casebook.models import Case, FeatureFile
from src.casebook.service.case_service import case_key, filtered_cases

CASE_NUMBERS_SHOWN = 200
TEST_KEYS_SHOWN = 200
PRIORITIES = ("low", "medium", "high", "critical")  # lowest first: the rank is the index
STATUSES = ("draft", "ready", "archived")


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
    sub = query.with_entities(Case.id, Case.feature_name, Case.source_path, Case.priority, Case.status,
                              Case.automated_test_key).subquery()
    rank = case(*[(sub.c.priority == p, i) for i, p in enumerate(PRIORITIES)], else_=-1)
    count_status = [func.coalesce(func.sum(case((sub.c.status == s, 1), else_=0)), 0) for s in STATUSES]
    groups = db.query(
        sub.c.feature_name, sub.c.source_path, func.count(sub.c.id),
        func.count(sub.c.automated_test_key), func.max(rank), *count_status,
    ).group_by(sub.c.feature_name, sub.c.source_path).all()
    groups.sort(key=lambda g: (g[1] is None, folder_of(g[1]) or "", (g[0] or "").casefold(), g[1] or ""))
    page = groups[offset:offset + limit]
    numbers = defaultdict(list)
    keys = defaultdict(set)
    if page:
        wanted = or_(*[and_(Case.feature_name == name if name is not None else Case.feature_name.is_(None),
                            Case.source_path == path if path is not None else Case.source_path.is_(None))
                       for name, path, *_ in page])
        rows = query.filter(wanted).order_by(Case.number).with_entities(
            Case.number, Case.feature_name, Case.source_path, Case.automated_test_key).all()
        for number, name, path, test_key in rows:
            numbers[(name, path)].append(number)
            if test_key:
                keys[(name, path)].add(test_key)
    stored = set()
    paths = [p for _, p, *_ in page if p is not None]
    if paths:
        stored = {p for (p,) in db.query(FeatureFile.path).filter(
            FeatureFile.project_id == project_id, FeatureFile.path.in_(paths)).all()}
    items = [{"feature_name": name, "path": path, "folder": folder_of(path), "case_count": count,
              "case_numbers": numbers[(name, path)][:CASE_NUMBERS_SHOWN],
              "test_keys": sorted(keys[(name, path)])[:TEST_KEYS_SHOWN], "has_source": path in stored,
              "linked_count": linked, "top_priority": PRIORITIES[top] if top >= 0 else None,
              "status_counts": dict(zip(STATUSES, (int(n) for n in per_status)))}
             for name, path, count, linked, top, *per_status in page]
    return {"total": len(groups), "items": items}


def _heading_keywords() -> str:
    """Every language's Scenario / Scenario Outline / Example keyword, as a regex alternation."""
    words = {w.strip() for spec in DIALECTS.values() for key in ("scenario", "scenarioOutline") for w in spec[key]}
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True) if w)


HEADING = re.compile(r"^[ \t]*(?:" + _heading_keywords() + r")[ \t]*:[ \t]*(.*?)[ \t]*$")
LINE_BREAK = re.compile(r"\r\n|\r|\n")


def scenario_lines(content: str) -> dict:
    """Fallback for cases imported before scenario_line: scenario name -> 1-based line of its heading in the
    raw text. Only a real heading counts (a scenario keyword after the indentation, any language), so
    step lines and doc string contents that repeat the name do not. The first heading of a name wins."""
    found: dict = {}
    fence = None  # the doc string delimiter we are inside, if any
    for number, text in enumerate(LINE_BREAK.split(content.lstrip("\ufeff")), start=1):
        stripped = text.strip()
        if fence is None and stripped.startswith(('"""', "```")):
            fence = stripped[:3]
            continue
        if fence is not None:
            fence = None if stripped.startswith(fence) else fence
            continue
        match = HEADING.match(text)
        if match:
            found.setdefault(match.group(1), number)
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
    fallback = scenario_lines(file.content) if file and any(c.scenario_line is None for c in cases) else {}
    lines = {c.number: c.scenario_line if c.scenario_line is not None else fallback.get(c.scenario_name)
             for c in cases}
    # File order by line; a case with no line goes last, by number
    cases.sort(key=lambda c: (lines[c.number] is None, lines[c.number] or 0, c.number))
    return {
        "feature_name": feature_name, "path": path,
        "folder": folder_of(path), "content": file.content if file else None,
        "imported_at": file.imported_at if file else None,
        "cases": [{"number": c.number, "key": case_key(c.number), "title": c.title,
                   "scenario_name": c.scenario_name, "status": c.status, "priority": c.priority,
                   "automated_test_key": c.automated_test_key, "line": lines[c.number]} for c in cases],
    }
