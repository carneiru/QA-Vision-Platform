"""Build qav-collector.pyz: a single-file build for CI runners without pip.

The collector is stdlib-only, so the archive runs anywhere a Python 3.9+
interpreter exists:  python qav-collector.pyz upload "reports/**/*.xml"
"""
import argparse
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "qav_collector"
MAIN = "from qav_collector.cli import main\nraise SystemExit(main())\n"


def build(out: Path) -> None:
    with tempfile.TemporaryDirectory() as staging:
        root = Path(staging)
        shutil.copytree(
            PACKAGE, root / "qav_collector",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (root / "__main__.py").write_text(MAIN, encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(root, out, interpreter="/usr/bin/env python3", compressed=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist/qav-collector.pyz", type=Path)
    args = parser.parse_args()
    build(args.out)
    print(f"built {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
