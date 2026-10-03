"""One entry point for every report format: the XML root element picks the
parser. JUnit stays in junit.py; TRX (vstest), NUnit 3, xUnit.net v2 and
TestNG live here, all producing the same result-dict shape. TRX wraps its
elements in a namespace, so matching is on the local name throughout."""
from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Iterator, Optional
from xml.parsers import expat

from qav_collector.junit import (
    CLASS_NAME_LENGTH, MAX_DURATION_MS, MAX_FILE_BYTES, NAME_LENGTH, SUITE_LENGTH,
    ParsedFile, _cut, _first_line, _read_xml, _Refused, _seconds, _skip, _timestamp, _walk,
)

_TRX_DURATION = re.compile(r"^(\d+):(\d\d):(\d\d(?:\.\d+)?)$")

_ROOTS = "<testsuites>, <testsuite>, <TestRun> (TRX), <test-run> (NUnit 3), <assemblies> (xUnit.net) or <testng-results>"


def parse_file(path: str) -> ParsedFile:
    parsed = ParsedFile(path=path)
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return _skip(parsed, "larger than 50 MB")
        root = _read_xml(path)
    except _Refused as exc:
        return _skip(parsed, str(exc))
    except expat.ExpatError as exc:
        return _skip(parsed, f"not well-formed XML ({expat.ErrorString(exc.code)}, line {exc.lineno})")
    except OSError as exc:
        return _skip(parsed, f"cannot be read ({exc.strerror or exc})")

    tag = _local(root.tag)
    if tag in ("testsuites", "testsuite"):
        _walk(root, "", False, parsed)
    elif tag == "TestRun":
        _trx(root, parsed)
    elif tag == "test-run":
        _nunit(root, parsed)
    elif tag == "assemblies":
        _xunit(root, parsed)
    elif tag == "testng-results":
        _testng(root, parsed)
    else:
        return _skip(parsed, f"root element is <{tag}>, not one of {_ROOTS}")
    if parsed.unnamed:
        parsed.warnings.append(f"skipped {parsed.unnamed} test case(s) without a name in {path}")
    return parsed


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_all(element: ET.Element, *names: str) -> Iterator[ET.Element]:
    """Descendants matched on local name, in document order."""
    for child in element.iter():
        if _local(child.tag) in names:
            yield child


def _text_of(element: Optional[ET.Element]) -> str:
    return "".join(element.itertext()) if element is not None else ""


def _row(suite: str, class_name: str, name: str, status: str, seconds: float) -> dict:
    return {
        "suite": suite[:SUITE_LENGTH],
        "class_name": class_name[:CLASS_NAME_LENGTH],
        "name": name[:NAME_LENGTH],
        "status": status,
        "duration_ms": round(min(seconds, MAX_DURATION_MS / 1000) * 1000),
    }


def _attach(row: dict, message: str, details: str) -> dict:
    message = message.strip() or _first_line(details)
    if message:
        row["message"] = _cut(message)
    if details.strip():
        row["details"] = _cut(details)
    return row


# --- TRX (Visual Studio / vstest) -------------------------------------------

_TRX_OUTCOMES = {
    "Passed": "passed", "Warning": "passed",
    "Failed": "failed", "Timeout": "failed",
    "Error": "errored", "Aborted": "errored",
}


def _trx(root: ET.Element, parsed: ParsedFile) -> None:
    classes = {}
    for definition in _find_all(root, "UnitTest"):
        method = next(_find_all(definition, "TestMethod"), None)
        if method is not None:
            classes[definition.get("id", "")] = method.get("className", "")

    for times in _find_all(root, "Times"):
        start, finish = _timestamp(times.get("start")), _timestamp(times.get("finish"))
        if start is not None:
            parsed.suite_timestamps.append(start)
            if finish is not None and finish >= start:
                parsed.suite_seconds += (finish - start).total_seconds()

    for result in _find_all(root, "UnitTestResult"):
        name = (result.get("testName") or "").strip()
        if not name:
            parsed.unnamed += 1
            continue
        row = _row(
            "", classes.get(result.get("testId", ""), ""), name,
            _TRX_OUTCOMES.get(result.get("outcome", ""), "skipped"),
            _trx_seconds(result.get("duration")),
        )
        error = next(_find_all(result, "ErrorInfo"), None)
        if error is not None:
            message = _text_of(next(_find_all(error, "Message"), None))
            stack = _text_of(next(_find_all(error, "StackTrace"), None))
            _attach(row, message, "\n".join(part for part in (message, stack) if part.strip()))
        parsed.results.append(row)


def _trx_seconds(value: Optional[str]) -> float:
    match = _TRX_DURATION.match((value or "").strip())
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


# --- NUnit 3 -----------------------------------------------------------------


def _nunit(root: ET.Element, parsed: ParsedFile) -> None:
    stamp = _timestamp(root.get("start-time"))
    if stamp is not None:
        parsed.suite_timestamps.append(stamp)
    parsed.suite_seconds += _seconds(root.get("duration"))

    assemblies = {
        suite: suite.get("name", "")
        for suite in _find_all(root, "test-suite") if suite.get("type") == "Assembly"
    }

    def assembly_of(case: ET.Element, element: ET.Element, inherited: str) -> str:
        if element in assemblies:
            inherited = assemblies[element]
        for child in element:
            if child is case:
                return inherited
            found = assembly_of(case, child, inherited)
            if found is not None:
                return found
        return None  # type: ignore[return-value]  # case not under this element

    for case in _find_all(root, "test-case"):
        name = (case.get("name") or "").strip()
        if not name:
            parsed.unnamed += 1
            continue
        result = case.get("result", "")
        if result == "Passed" or result == "Warning":
            status = "passed"
        elif result == "Failed":
            status = "errored" if case.get("label") == "Error" else "failed"
        else:  # Skipped, Inconclusive, anything new
            status = "skipped"
        row = _row(
            assembly_of(case, root, "") or "", case.get("classname", ""), name,
            status, _seconds(case.get("duration")),
        )
        failure = next(_find_all(case, "failure"), None)
        if failure is not None:
            message = _text_of(next(_find_all(failure, "message"), None))
            stack = _text_of(next(_find_all(failure, "stack-trace"), None))
            _attach(row, message, "\n".join(part for part in (message, stack) if part.strip()))
        parsed.results.append(row)


# --- xUnit.net v2 -------------------------------------------------------------


def _xunit(root: ET.Element, parsed: ParsedFile) -> None:
    for assembly in _find_all(root, "assembly"):
        suite = os.path.basename((assembly.get("name") or "").replace("\\", "/"))
        parsed.suite_seconds += _seconds(assembly.get("time"))
        stamp = _timestamp(f"{assembly.get('run-date', '')}T{assembly.get('run-time', '')}")
        if stamp is not None:
            parsed.suite_timestamps.append(stamp)
        for test in _find_all(assembly, "test"):
            method = (test.get("method") or test.get("name") or "").strip()
            if not method:
                parsed.unnamed += 1
                continue
            status = {"Pass": "passed", "Fail": "failed"}.get(test.get("result", ""), "skipped")
            row = _row(suite, test.get("type", ""), method, status, _seconds(test.get("time")))
            failure = next(_find_all(test, "failure"), None)
            if failure is not None:
                message = _text_of(next(_find_all(failure, "message"), None))
                stack = _text_of(next(_find_all(failure, "stack-trace"), None))
                _attach(row, message, "\n".join(part for part in (message, stack) if part.strip()))
            elif status == "skipped":
                reason = _text_of(next(_find_all(test, "reason"), None))
                _attach(row, reason, "")
            parsed.results.append(row)


# --- TestNG -------------------------------------------------------------------


def _testng(root: ET.Element, parsed: ParsedFile) -> None:
    for suite in _find_all(root, "suite"):
        suite_name = suite.get("name", "")
        stamp = _timestamp(suite.get("started-at"))
        if stamp is not None:
            parsed.suite_timestamps.append(stamp)
        parsed.suite_seconds += _testng_ms(suite.get("duration-ms")) / 1000
        for klass in _find_all(suite, "class"):
            class_name = klass.get("name", "")
            for method in _find_all(klass, "test-method"):
                if (method.get("is-config") or "").lower() == "true":
                    continue  # setUp/tearDown are not tests
                name = (method.get("name") or "").strip()
                if not name:
                    parsed.unnamed += 1
                    continue
                status = {"PASS": "passed", "FAIL": "failed"}.get(method.get("status", ""), "skipped")
                row = _row(suite_name, class_name, name, status, _testng_ms(method.get("duration-ms")) / 1000)
                exception = next(_find_all(method, "exception"), None)
                if exception is not None:
                    message = _text_of(next(_find_all(exception, "message"), None))
                    stack = _text_of(next(_find_all(exception, "full-stacktrace"), None))
                    _attach(row, message, "\n".join(part for part in (message.strip(), stack.strip()) if part))
                parsed.results.append(row)


def _testng_ms(value: Optional[str]) -> float:
    try:
        ms = float(value or "")
    except ValueError:
        return 0.0
    return ms if math.isfinite(ms) and ms >= 0 else 0.0
