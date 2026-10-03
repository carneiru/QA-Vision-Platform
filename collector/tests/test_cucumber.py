"""Cucumber JSON (cucumber-jvm/js/rb classic formatter) through the same
dispatcher: a feature's scenarios become results in the shared shape."""
import json
from datetime import datetime, timezone

from qav_collector.formats import parse_file


def write(tmp_path, data, name="cucumber.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def by_name(parsed):
    return {r["name"]: r for r in parsed.results}


CUCUMBER = [
    {
        "uri": "features/checkout.feature",
        "name": "Checkout",
        "keyword": "Feature",
        "elements": [
            {
                "type": "background",
                "keyword": "Background",
                "name": "Signed in",
                "steps": [
                    {"keyword": "Given ", "name": "a signed-in shopper",
                     "result": {"status": "passed", "duration": 50_000_000}},
                ],
            },
            {
                "type": "scenario",
                "keyword": "Scenario",
                "name": "Pays with a stored card",
                "start_timestamp": "2026-10-01T10:00:00.000Z",
                "steps": [
                    {"keyword": "When ", "name": "the shopper pays",
                     "result": {"status": "passed", "duration": 1_400_000_000}},
                    {"keyword": "Then ", "name": "the order confirms",
                     "result": {"status": "passed", "duration": 50_000_000}},
                ],
            },
            {
                "type": "scenario",
                "keyword": "Scenario",
                "name": "Refunds",
                "steps": [
                    {"keyword": "When ", "name": "the shopper refunds",
                     "result": {"status": "failed", "duration": 200_000_000,
                                "error_message": "AssertionError: no refund button"}},
                    {"keyword": "Then ", "name": "the money returns",
                     "result": {"status": "skipped"}},
                ],
            },
            {
                "type": "scenario",
                "keyword": "Scenario",
                "name": "Gift wrap",
                "steps": [
                    {"keyword": "When ", "name": "the shopper wraps",
                     "result": {"status": "undefined"}},
                ],
            },
        ],
    },
]


def test_cucumber_scenarios_become_results(tmp_path):
    parsed = parse_file(write(tmp_path, CUCUMBER))
    assert not parsed.skipped
    results = by_name(parsed)
    assert "Signed in" not in results  # background steps fold into the scenarios

    pays = results["Pays with a stored card"]
    assert pays["status"] == "passed"
    assert pays["suite"] == "Checkout"
    assert pays["class_name"] == "features/checkout.feature"
    # background 50ms + steps 1400ms + 50ms
    assert pays["duration_ms"] == 1500

    refunds = results["Refunds"]
    assert refunds["status"] == "failed"
    assert refunds["message"] == "AssertionError: no refund button"
    assert "the shopper refunds" in refunds["details"]

    assert results["Gift wrap"]["status"] == "skipped"
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]


def test_non_cucumber_json_is_skipped_with_a_reason(tmp_path):
    parsed = parse_file(write(tmp_path, {"not": "cucumber"}))
    assert parsed.skipped
    assert "not Cucumber JSON" in parsed.warnings[0]


def test_broken_json_is_skipped(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("[{", encoding="utf-8")
    parsed = parse_file(str(path))
    assert parsed.skipped
