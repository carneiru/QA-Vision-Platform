"""Parsed scenarios + the project's imported cases -> what an import would do (ADR-023). Pure."""
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.casebook.gherkin_import.parse import Issue, ParsedFile, ParsedScenario

SUMMARY_NAMES = {"create": "created", "update": "updated", "move": "moved", "reactivate": "reactivated",
                 "archive": "archived", "unchanged": "unchanged", "skip": "skipped"}


@dataclass
class Item:
    action: str
    path: str
    scenario: Optional[str]
    case_id: Optional[int] = None
    case_number: Optional[int] = None
    parsed: Optional[ParsedScenario] = None


@dataclass
class Plan:
    items: List[Item]
    errors: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    plan_hash: str = ""

    def summary(self) -> dict:
        counts = {name: 0 for name in SUMMARY_NAMES.values()}
        for item in self.items:
            counts[SUMMARY_NAMES[item.action]] += 1
        return counts


@dataclass(frozen=True)
class Existing:
    id: int
    number: int
    source_key: str
    source_path: str
    status: str
    title: str
    gherkin: str
    labels: tuple
    priority: str


def _differs(case: Existing, scenario: ParsedScenario) -> bool:
    return (
        case.title != scenario.title or case.gherkin != scenario.gherkin or case.labels != scenario.labels
        or (scenario.priority is not None and scenario.priority != case.priority)
    )


def plan_hash(items: List[Item]) -> str:
    """Over the sorted actions, so the order files arrived in never changes it."""
    rows = sorted([i.action, i.path, i.scenario or "", i.case_number or 0] for i in items)
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_plan(files: List[ParsedFile], existing: List[Existing], full: bool) -> Plan:
    plan = Plan(items=[])
    by_key: Dict[str, Existing] = {c.source_key: c for c in existing}
    uploaded = {f.path for f in files}
    broken = {f.path for f in files if f.errors}
    incoming: Dict[str, ParsedScenario] = {}
    for parsed_file in files:
        plan.errors += parsed_file.errors
        plan.warnings += parsed_file.warnings
        if parsed_file.errors:
            plan.items.append(Item("skip", parsed_file.path, None))
        for warning in parsed_file.warnings:
            if warning.skipped:
                plan.items.append(Item("skip", parsed_file.path, None))
        for scenario in parsed_file.scenarios:
            incoming[scenario.source_key] = scenario

    creates: List[ParsedScenario] = []
    for key, scenario in incoming.items():
        case = by_key.get(key)
        if case is None:
            creates.append(scenario)
            continue
        if case.status == "archived":
            action = "reactivate"
        elif _differs(case, scenario):
            action = "update"
        else:
            action = "unchanged"
        plan.items.append(Item(action, scenario.path, scenario.name, case.id, case.number, scenario))

    gone = [
        c for c in existing
        if c.source_key not in incoming and c.status != "archived" and c.source_path not in broken
        and (c.source_path in uploaded or full)
    ]

    # A move: exactly one gone case and exactly one new scenario share the same Gherkin text
    gone_by_text, new_by_text = defaultdict(list), defaultdict(list)
    for case in gone:
        gone_by_text[case.gherkin].append(case)
    for scenario in creates:
        new_by_text[scenario.gherkin].append(scenario)
    moved_cases, moved_scenarios = set(), set()
    for text, cases in gone_by_text.items():
        scenarios = new_by_text.get(text, [])
        if len(cases) == 1 and len(scenarios) == 1:
            case, scenario = cases[0], scenarios[0]
            plan.items.append(Item("move", scenario.path, scenario.name, case.id, case.number, scenario))
            moved_cases.add(case.id)
            moved_scenarios.add(scenario.source_key)

    for scenario in creates:
        if scenario.source_key not in moved_scenarios:
            plan.items.append(Item("create", scenario.path, scenario.name, parsed=scenario))
    for case in gone:
        if case.id not in moved_cases:
            plan.items.append(Item("archive", case.source_path, case.title, case.id, case.number))

    plan.items.sort(key=lambda i: (i.path, i.scenario or "", i.action))
    plan.plan_hash = plan_hash(plan.items)
    return plan
