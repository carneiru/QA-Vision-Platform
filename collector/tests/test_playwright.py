"""Playwright's own JSON reporter (--reporter=json): specs become results,
every retry attempt kept as its own result, like Surefire reruns."""
import json
from datetime import datetime, timezone

from qeos_collector.formats import parse_file


def write(tmp_path, data):
    path = tmp_path / "playwright.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


PLAYWRIGHT = {
    "config": {"version": "1.47.0"},
    "suites": [
        {
            "title": "checkout.spec.ts",
            "file": "checkout.spec.ts",
            "specs": [],
            "suites": [
                {
                    "title": "Checkout",
                    "file": "checkout.spec.ts",
                    "specs": [
                        {
                            "title": "pays with a stored card",
                            "file": "checkout.spec.ts",
                            "tests": [
                                {
                                    "projectName": "chromium",
                                    "status": "expected",
                                    "results": [
                                        {"status": "passed", "duration": 1400,
                                         "startTime": "2026-10-01T10:00:00.000Z", "retry": 0},
                                    ],
                                },
                            ],
                        },
                        {
                            "title": "refunds",
                            "file": "checkout.spec.ts",
                            "tests": [
                                {
                                    "projectName": "chromium",
                                    "status": "flaky",
                                    "results": [
                                        {"status": "failed", "duration": 900, "retry": 0,
                                         "error": {"message": "expect(received).toBe(expected)"}},
                                        {"status": "passed", "duration": 800, "retry": 1},
                                    ],
                                },
                            ],
                        },
                        {
                            "title": "gift wrap",
                            "file": "checkout.spec.ts",
                            "tests": [
                                {
                                    "projectName": "firefox",
                                    "status": "skipped",
                                    "results": [{"status": "skipped", "duration": 0, "retry": 0}],
                                },
                            ],
                        },
                        {
                            "title": "times out",
                            "file": "checkout.spec.ts",
                            "tests": [
                                {
                                    "projectName": "chromium",
                                    "status": "unexpected",
                                    "results": [
                                        {"status": "timedOut", "duration": 30000, "retry": 0,
                                         "errors": [{"message": "Test timeout of 30000ms exceeded."}]},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    ],
}


def test_playwright_specs_become_results(tmp_path):
    parsed = parse_file(write(tmp_path, PLAYWRIGHT))
    assert not parsed.skipped

    rows = [(r["name"], r["status"], r["duration_ms"]) for r in parsed.results]
    assert ("pays with a stored card", "passed", 1400) in rows
    # the flaky spec keeps BOTH attempts: fail then pass, visible to flaky detection
    assert ("refunds", "failed", 900) in rows
    assert ("refunds", "passed", 800) in rows
    assert ("gift wrap", "skipped", 0) in rows
    assert ("times out", "failed", 30000) in rows

    by = {(r["name"], r["status"]): r for r in parsed.results}
    first = by[("refunds", "failed")]
    assert first["suite"] == "chromium"
    assert first["class_name"] == "checkout.spec.ts"
    assert first["message"] == "expect(received).toBe(expected)"
    assert by[("times out", "failed")]["message"] == "Test timeout of 30000ms exceeded."
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]


def test_playwright_json_without_suites_is_skipped(tmp_path):
    parsed = parse_file(write(tmp_path, {"config": {}, "stats": {}}))
    assert parsed.skipped
