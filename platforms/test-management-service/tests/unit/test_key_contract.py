"""The import must compute the very key ingestion stores for the same scenario (ADR-023).

The collector has no dependencies, so its parser is loaded straight from the repository."""
import json
import sys
from pathlib import Path

from qav_shared.keys import test_key
from src.casebook.gherkin_import.parse import parse_feature

REPO = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
sys.path.insert(0, str(REPO / "collector" / "src"))
from qav_collector.formats import parse_file  # noqa: E402


def test_imported_cases_link_to_the_keys_results_are_stored_under():
    rows = parse_file(str(FIXTURES / "cucumber_report.json")).results
    stored = {test_key(r["suite"], r["class_name"], r["name"]) for r in rows}
    feature = (FIXTURES / "checkout.feature").read_text(encoding="utf-8")
    imported = parse_feature("tests/features/checkout.feature", feature).scenarios
    assert {s.test_key for s in imported} <= stored
    assert len(imported) == 3


def test_a_report_written_on_windows_links_to_the_same_cases(tmp_path):
    report = json.loads((FIXTURES / "cucumber_report.json").read_text(encoding="utf-8"))
    report[0]["uri"] = report[0]["uri"].replace("/", "\\")
    windows = tmp_path / "cucumber_report.json"
    windows.write_text(json.dumps(report), encoding="utf-8")
    stored = {test_key(r["suite"], r["class_name"], r["name"]) for r in parse_file(str(windows)).results}
    feature = (FIXTURES / "checkout.feature").read_text(encoding="utf-8")
    imported = {s.name: s.test_key for s in parse_feature("tests/features/checkout.feature", feature).scenarios}
    assert set(imported.values()) <= stored
    # the outline links through its first Examples row
    assert imported["Apply <code>"] == test_key("Checkout", "tests/features/checkout.feature", "Apply SAVE10")
