"""GET /case-areas: every active case, dictionary-encoded, for the report's joins (spec: test-management)."""
import time

import httpx
import pytest
from sqlalchemy import insert

from src.casebook.models import Case, CaseLabel, Suite, SuiteCase
from src.casebook.service import case_area_service

P = "/api/v1/projects/1"
KEY = "ab" * 32


def add_case(db, number, *, title=None, source_path=None, feature=None, key=None, status="ready", labels=(),
             project_id=1):
    row = Case(project_id=project_id, number=number, title=title or f"case {number}", steps=[], status=status,
               source_path=source_path, feature_name=feature, automated_test_key=key, created_by=1,
               labels=[CaseLabel(label=label) for label in labels])
    db.add(row)
    db.flush()
    return row


def add_suite(db, name, cases, project_id=1):
    suite = Suite(project_id=project_id, name=name, created_by=1)
    db.add(suite)
    db.flush()
    for position, case in enumerate(cases):
        db.add(SuiteCase(suite_id=suite.id, case_id=case.id, position=position))
    return suite


@pytest.fixture
def seeded(db, project_role):
    project_role("viewer")
    a = add_case(db, 1, title="Book one-way", source_path="features/booking/air/a.feature", feature="Air booking",
                 key=KEY.upper(), labels=("smoke", "ado-12"))
    b = add_case(db, 2, source_path="features/booking/b.feature", feature="Booking", key="cd" * 32, labels=("smoke",))
    add_case(db, 3, source_path="root.feature", feature="Root", key="ef" * 32)
    m = add_case(db, 4, title="manual check")
    add_case(db, 5, source_path="features/old/x.feature", feature="Old", status="archived", labels=("legacy",))
    add_case(db, 6, status="draft", title="draft manual")
    add_case(db, 7, project_id=2, source_path="other/z.feature", feature="Other")
    add_suite(db, "Regression", [a, b])
    add_suite(db, "Nightly", [a, m])
    add_suite(db, "Empty", [])
    db.commit()


def areas(client, auth):
    response = client.get(f"{P}/case-areas", headers=auth())
    assert response.status_code == 200, response.text
    return response.json()


def test_active_cases_with_sorted_dictionaries(client, auth, seeded):
    body = areas(client, auth)
    assert body["counts"] == {"cases": 5, "linked": 3, "manual": 2}            # archived 5 left out, draft 6 kept
    assert body["folders"] == ["features/booking", "features/booking/air"]     # root.feature has no folder
    assert body["features"] == ["Air booking", "Booking", "Root"]
    assert body["labels"] == ["ado-12", "smoke"]                               # "legacy" only on an archived case
    assert body["suites"] == [{"id": 3, "name": "Empty"}, {"id": 2, "name": "Nightly"}, {"id": 1, "name": "Regression"}]
    assert [c["n"] for c in body["cases"]] == [1, 2, 3, 4, 6]
    assert body["generated_at"].endswith("Z")


def test_each_case_points_into_the_dictionaries(client, auth, seeded):
    body = areas(client, auth)
    cases = {c["n"]: c for c in body["cases"]}
    one = cases[1]
    assert one["t"] == "Book one-way" and one["k"] == KEY                      # lower-cased
    assert body["folders"][one["fo"]] == "features/booking/air"
    assert body["features"][one["fe"]] == "Air booking"
    assert [body["labels"][i] for i in one["l"]] == ["ado-12", "smoke"]
    assert sorted(body["suites"][i]["name"] for i in one["s"]) == ["Nightly", "Regression"]
    assert cases[3]["fo"] is None and body["features"][cases[3]["fe"]] == "Root"
    assert (cases[4]["k"], cases[4]["fo"], cases[4]["fe"], cases[4]["l"]) == (None, None, None, [])
    assert [body["suites"][i]["name"] for i in cases[4]["s"]] == ["Nightly"]


def test_every_role_reads_and_other_projects_are_invisible(client, auth, seeded, project_role):
    for role in ("owner", "admin", "member", "viewer", "billing_manager"):
        project_role(role)
        assert client.get(f"{P}/case-areas", headers=auth()).status_code == 200
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get(f"{P}/case-areas", headers=auth()).status_code == 404
    assert client.get(f"{P}/case-areas").status_code == 401


def test_too_many_cases_is_409(client, auth, seeded, monkeypatch):
    monkeypatch.setattr(case_area_service, "MAX_CASES", 4)
    response = client.get(f"{P}/case-areas", headers=auth())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "too_many_cases"


def test_twenty_thousand_cases_answer_quickly(client, auth, db, project_role):
    project_role()
    db.execute(insert(Case), [
        {"project_id": 1, "number": n, "title": f"Scenario {n}", "steps": [], "status": "ready", "created_by": 1,
         "source_path": f"features/area{n % 40}/f{n % 400}.feature", "feature_name": f"Feature {n % 400}",
         "automated_test_key": f"{n:064x}"}
        for n in range(1, 20_001)
    ])
    db.commit()
    started = time.perf_counter()
    body = areas(client, auth)
    elapsed = time.perf_counter() - started
    assert body["counts"]["cases"] == 20_000
    assert elapsed < 5.0  # SQLite on a CI runner; the PostgreSQL target (300 ms) is checked by hand
