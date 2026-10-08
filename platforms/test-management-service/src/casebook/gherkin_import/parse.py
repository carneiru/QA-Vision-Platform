"""A .feature file -> the cases it holds (docs/superpowers/specs/2026-10-06-gherkin-import-design.md).

Pure: no database. Uses Cucumber's own parser, so scenarios are seen exactly as runners see them."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from gherkin.errors import CompositeParserException, ParserError
from gherkin.parser import Parser

from qeos_shared.keys import test_key

PRIORITIES = ("low", "medium", "high", "critical")
LABEL = re.compile(r"^[a-z0-9._-]{1,40}$")
MAX_LABELS = 20
TITLE_LENGTH = 200
DESCRIPTION_LENGTH = 10000
PLACEHOLDER = re.compile(r"<([^<>]+)>")
INDENT = "  "


@dataclass(frozen=True)
class Issue:
    path: str
    line: Optional[int]
    message: str
    skipped: bool = False  # True when the warning means a scenario was not imported


@dataclass(frozen=True)
class ParsedScenario:
    path: str
    feature_name: str
    name: str
    title: str
    gherkin: str
    description: Optional[str]
    labels: tuple
    priority: Optional[str]
    source_key: str
    test_key: str
    test_name: str
    line: int


@dataclass
class ParsedFile:
    path: str
    feature_name: str = ""
    scenarios: List[ParsedScenario] = field(default_factory=list)
    errors: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)


def source_key(path: str, name: str) -> str:
    return hashlib.sha256(f"{path}\0{name}".encode("utf-8")).hexdigest()


def parse_feature(path: str, content: str) -> ParsedFile:
    result = ParsedFile(path=path)
    if content.startswith("\ufeff"):
        content = content[1:]  # editors on Windows often save a byte-order mark; the parser rejects it
    try:
        document = Parser().parse(content)
    except CompositeParserException as exc:
        for error in exc.errors:
            result.errors.append(Issue(path, _line(error), str(error)))
        return result
    except ParserError as exc:
        result.errors.append(Issue(path, _line(exc), str(exc)))
        return result
    feature = document.get("feature")
    if not feature:
        return result
    feature_name = (feature.get("name") or "").strip()
    result.feature_name = feature_name
    seen: set = set()
    for child in feature.get("children", []):
        if "background" in child:
            continue
        if "rule" in child:
            rule = child["rule"]
            for rule_child in rule.get("children", []):
                if "scenario" in rule_child:
                    _add(result, seen, feature, feature_name, rule, rule_child["scenario"])
        elif "scenario" in child:
            _add(result, seen, feature, feature_name, None, child["scenario"])
    return result


def _line(error) -> Optional[int]:
    location = getattr(error, "location", None) or {}
    return location.get("line")


def _background_steps(children: Iterable[dict]) -> list:
    return [step for child in children if "background" in child for step in child["background"]["steps"]]


def _add(result: ParsedFile, seen: set, feature: dict, feature_name: str, rule: Optional[dict],
         scenario: dict) -> None:
    name = (scenario.get("name") or "").strip()
    line = scenario["location"]["line"]
    if not name:
        result.warnings.append(Issue(result.path, line, "skipped a scenario without a name", skipped=True))
        return
    if name in seen:
        result.warnings.append(Issue(result.path, line,
                                     f'skipped "{name}": another scenario in this file has the same name',
                                     skipped=True))
        return
    seen.add(name)

    tags = list(feature.get("tags", [])) + list((rule or {}).get("tags", [])) + list(scenario.get("tags", []))
    labels, priority = _labels_and_priority(result, line, [t["name"] for t in tags])
    background = _background_steps(feature.get("children", []))
    if rule is not None:
        background += _background_steps(rule.get("children", []))
    # The collector cuts suite to 500 and name to 1000 characters before hashing
    # (collector/src/qeos_collector/junit.py), so a scenario name over 1000 characters never links
    test_name = _first_example_name(name, scenario)
    description = (scenario.get("description") or "").strip() or None
    result.scenarios.append(ParsedScenario(
        path=result.path, feature_name=feature_name, name=name, title=name[:TITLE_LENGTH],
        gherkin=_render(background, scenario), description=description[:DESCRIPTION_LENGTH] if description else None,
        labels=labels, priority=priority, source_key=source_key(result.path, name),
        test_key=test_key(feature_name, result.path, test_name), test_name=test_name, line=line,
    ))


def _labels_and_priority(result: ParsedFile, line: int, tags: List[str]):
    labels: list = []
    priority = None
    for tag in tags:
        bare = tag[1:] if tag.startswith("@") else tag
        if bare.lower().startswith("priority:") and bare.split(":", 1)[1].lower() in PRIORITIES:
            priority = bare.split(":", 1)[1].lower()  # later tags (rule, scenario) win
            continue
        label = bare.lower().replace(":", "-")
        if not LABEL.match(label):
            result.warnings.append(Issue(result.path, line, f"skipped tag {tag}: not a valid label"))
            continue
        if label not in labels:
            labels.append(label)
    if len(labels) > MAX_LABELS:
        result.warnings.append(Issue(result.path, line, f"kept the first {MAX_LABELS} of {len(labels)} tags"))
        labels = labels[:MAX_LABELS]
    return tuple(sorted(labels)), priority


def _first_example_name(name: str, scenario: dict) -> str:
    """cucumber-js names an outline's rows after the outline, with <placeholders> filled from the row."""
    if not PLACEHOLDER.search(name):
        return name
    for examples in scenario.get("examples", []):
        header = examples.get("tableHeader")
        body = examples.get("tableBody") or []
        if header and body:
            values = {h["value"]: c["value"] for h, c in zip(header["cells"], body[0]["cells"])}
            return PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), name)
    return name


def _cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "\\n")


def _row(cells: list, indent: str) -> str:
    return indent + "| " + " | ".join(_cell(c["value"]) for c in cells) + " |"


def _steps(steps: list, indent: str) -> List[str]:
    lines = []
    for step in steps:
        lines.append(f"{indent}{step['keyword']}{step['text']}")
        inner = indent + INDENT
        if "dataTable" in step:
            lines += [_row(r["cells"], inner) for r in step["dataTable"]["rows"]]
        if "docString" in step:
            doc = step["docString"]
            fence = doc.get("delimiter", '"""')
            lines.append(f"{inner}{fence}{doc.get('mediaType') or ''}")
            lines += [f"{inner}{text}" if text else "" for text in doc["content"].split("\n")]
            lines.append(f"{inner}{fence}")
    return lines


def _render(background: list, scenario: dict) -> str:
    lines: List[str] = []
    if background:
        lines.append("Background:")
        lines += _steps(background, INDENT)
    lines.append(f"{scenario['keyword']}: {scenario['name'].strip()}")
    lines += _steps(scenario.get("steps", []), INDENT)
    for examples in scenario.get("examples", []):
        title = (examples.get("name") or "").strip()
        lines.append(f"{INDENT}{examples['keyword']}:" + (f" {title}" if title else ""))
        if examples.get("tableHeader"):
            lines.append(_row(examples["tableHeader"]["cells"], INDENT * 2))
        lines += [_row(r["cells"], INDENT * 2) for r in examples.get("tableBody") or []]
    return "\n".join(lines)
