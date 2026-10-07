"""The zipapp build: one .pyz file for runners without pip. Stdlib only, so
the archive needs nothing but a Python 3.9+ interpreter."""
import subprocess
import sys
from pathlib import Path

from qeos_collector import __version__

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_zipapp.py"


def build(tmp_path):
    out = tmp_path / "qeos-collector.pyz"
    result = subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return out


def test_the_archive_runs_and_names_its_version(tmp_path):
    out = build(tmp_path)
    result = subprocess.run([sys.executable, str(out), "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"qeos-collector {__version__}"


def test_the_archive_parses_and_dry_runs(tmp_path):
    out = build(tmp_path)
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite name="s"><testcase classname="c" name="ok" time="0.1"/></testsuite>',
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(out), "upload", str(report), "--dry-run"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"name": "ok"' in result.stdout
    assert "dry run: 1 part(s), nothing uploaded" in result.stderr


def test_no_pycache_ships_in_the_archive(tmp_path):
    import zipfile

    out = build(tmp_path)
    names = zipfile.ZipFile(out).namelist()
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    assert "qeos_collector/cli.py" in names
    assert "__main__.py" in names
