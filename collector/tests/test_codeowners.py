"""CODEOWNERS: each result whose `file` matches a pattern carries its owners.
Git-style matching — last matching line wins, `*` stays inside one path
segment, `**` crosses, a leading `/` anchors to the repo root."""

from qeos_collector.codeowners import load_codeowners

CODEOWNERS = """
# Comments and blank lines are ignored

*                 @org/default-team
*.py              @org/python-team
/src/payments/    @org/payments @alice@example.com
docs/             @org/docs-team
tests/**/fixtures/*.xml  @org/qa-team
/README.md        @bob@example.com
"""


def matcher(tmp_path):
    (tmp_path / "CODEOWNERS").write_text(CODEOWNERS, encoding="utf-8")
    return load_codeowners(str(tmp_path))


def test_last_matching_line_wins(tmp_path):
    owners = matcher(tmp_path)
    assert owners("src/payments/charge.py") == "@org/payments @alice@example.com"
    assert owners("src/other/module.py") == "@org/python-team"
    assert owners("README.md") == "@bob@example.com"
    assert owners("anything.txt") == "@org/default-team"


def test_directory_pattern_matches_anywhere_without_a_slash_prefix(tmp_path):
    owners = matcher(tmp_path)
    assert owners("docs/guide.md") == "@org/docs-team"
    assert owners("site/docs/guide.md") == "@org/docs-team"


def test_double_star_crosses_directories_and_star_does_not(tmp_path):
    owners = matcher(tmp_path)
    assert owners("tests/a/b/fixtures/report.xml") == "@org/qa-team"
    # *.py must not match a path separator: src/x.py/odd would be a dir
    assert owners("tests/fixtures/report.json") == "@org/default-team"


def test_github_location_and_missing_file(tmp_path):
    sub = tmp_path / ".github"
    sub.mkdir()
    (sub / "CODEOWNERS").write_text("*.md @org/writers\n", encoding="utf-8")
    owners = load_codeowners(str(tmp_path))
    assert owners("x.md") == "@org/writers"
    assert owners("x.py") is None

    empty = tmp_path / "empty"
    empty.mkdir()
    assert load_codeowners(str(empty))("anything") is None
