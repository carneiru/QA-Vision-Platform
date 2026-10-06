"""The import plan (pure) and its application to the database."""
import pytest

from src.casebook.gherkin_import.parse import parse_feature
from src.casebook.gherkin_import.plan import Existing, build_plan
from src.casebook.models import Case, CaseLabel
from src.casebook.service import import_service

A = "features/a.feature"
FEATURE = "Feature: A\n  @smoke\n  Scenario: one\n    Given x\n  Scenario: two\n    Given y\n"


def run(db, files, full=False, user=1):
    plan = import_service.plan_import(db, 1, files, full)
    return import_service.apply_plan(db, 1, user, plan)


def actions(plan):
    return sorted((i.action, i.path, i.scenario) for i in plan.items)


def test_first_import_creates_numbered_linked_cases(db):
    plan = run(db, [(A, FEATURE)])
    assert plan.summary()["created"] == 2
    one = db.query(Case).filter(Case.title == "one").one()
    assert (one.number, one.source_path, one.status) == (1, A, "draft")
    assert one.gherkin == "Scenario: one\n  Given x"
    assert [l.label for l in one.labels] == ["smoke"]
    assert one.automated_test_key and one.automated_name == "one"


def test_same_batch_twice_is_all_unchanged_and_hash_is_order_free(db):
    b = "features/b.feature"
    first = import_service.plan_import(db, 1, [(A, FEATURE), (b, "Feature: B\n  Scenario: s\n    Given z\n")], False)
    flipped = import_service.plan_import(db, 1, [(b, "Feature: B\n  Scenario: s\n    Given z\n"), (A, FEATURE)], False)
    assert first.plan_hash == flipped.plan_hash
    import_service.apply_plan(db, 1, 1, first)
    again = import_service.plan_import(db, 1, [(A, FEATURE), (b, "Feature: B\n  Scenario: s\n    Given z\n")], False)
    assert {i.action for i in again.items} == {"unchanged"}


def test_changed_steps_update_and_a_gone_scenario_is_archived(db):
    run(db, [(A, FEATURE)])
    plan = run(db, [(A, "Feature: A\n  Scenario: one\n    Given changed\n")])
    assert actions(plan) == [("archive", A, "two"), ("update", A, "one")]
    one = db.query(Case).filter(Case.title == "one").one()
    assert one.gherkin.endswith("Given changed") and one.labels == []
    assert db.query(Case).filter(Case.title == "two").one().status == "archived"


def test_update_keeping_one_label_and_adding_another_succeeds(db):
    run(db, [(A, "Feature: A\n  @smoke\n  Scenario: one\n    Given x\n")])
    run(db, [(A, "Feature: A\n  @smoke @extra\n  Scenario: one\n    Given x\n")])
    one = db.query(Case).one()
    assert sorted(l.label for l in one.labels) == ["extra", "smoke"]


def test_a_returning_scenario_is_reactivated_with_its_number(db):
    run(db, [(A, FEATURE)])
    run(db, [(A, "Feature: A\n  Scenario: one\n    Given x\n")])
    plan = run(db, [(A, FEATURE)])
    assert ("reactivate", A, "two") in actions(plan)
    two = db.query(Case).filter(Case.title == "two").one()
    assert (two.number, two.status) == (2, "draft")


def test_moving_a_file_keeps_numbers(db):
    run(db, [(A, FEATURE)])
    plan = run(db, [("features/moved/a.feature", FEATURE)], full=True)
    assert plan.summary()["moved"] == 2 and plan.summary()["created"] == 0
    one = db.query(Case).filter(Case.title == "one").one()
    assert (one.number, one.source_path) == (1, "features/moved/a.feature")


def test_ambiguous_moves_are_not_moves(db):
    twin = "Feature: A\n  Scenario: same\n    Given x\n"
    run(db, [("x/1.feature", twin), ("x/2.feature", twin)])
    plan = run(db, [("y/1.feature", twin), ("y/2.feature", twin)], full=True)
    assert plan.summary()["moved"] == 0
    assert plan.summary()["created"] == 2 and plan.summary()["archived"] == 2


def test_without_full_only_uploaded_paths_can_be_archived(db):
    run(db, [(A, FEATURE), ("features/b.feature", "Feature: B\n  Scenario: s\n    Given z\n")])
    partial = run(db, [(A, FEATURE)])
    assert partial.summary()["archived"] == 0
    full = run(db, [(A, FEATURE)], full=True)
    assert actions(full)[0] == ("archive", "features/b.feature", "s")


def test_a_broken_file_never_archives_its_cases(db):
    run(db, [(A, FEATURE)])
    plan = run(db, [(A, "Feature: A\n  Scenario: one\n    Given x\n  oops\n")], full=True)
    assert plan.summary()["archived"] == 0 and plan.errors
    assert plan.summary()["skipped"] == 1
    assert db.query(Case).filter(Case.status == "archived").count() == 0


def test_manual_cases_are_never_touched(db):
    db.add(Case(project_id=1, number=1, title="one", steps=[], created_by=1))
    db.commit()
    plan = run(db, [(A, FEATURE)], full=True)
    assert plan.summary()["created"] == 2
    manual = db.query(Case).filter(Case.source_key.is_(None)).one()
    assert manual.status == "draft"
    assert sorted(c.number for c in db.query(Case).all()) == [1, 2, 3]


def test_priority_tag_sets_priority_and_a_manual_link_is_kept(db):
    run(db, [(A, "Feature: A\n  @priority:critical\n  Scenario: one\n    Given x\n")])
    one = db.query(Case).one()
    assert one.priority == "critical"
    one.automated_test_key, one.automated_name = "f" * 64, "picked by hand"
    db.commit()
    run(db, [(A, "Feature: A\n  @priority:critical\n  Scenario: one\n    Given x2\n")])
    db.refresh(one)
    assert one.automated_test_key == "f" * 64


def test_dry_run_plan_writes_nothing_and_new_cases_have_no_number(db):
    plan = import_service.plan_import(db, 1, [(A, FEATURE)], False)
    assert db.query(Case).count() == 0
    assert all(i.case_number is None for i in plan.items)


def test_another_project_is_invisible(db):
    run(db, [(A, FEATURE)])
    plan = import_service.plan_import(db, 2, [(A, FEATURE)], True)
    assert plan.summary()["created"] == 2


@pytest.mark.parametrize("raw, clean", [
    ("tests\\features\\a.feature", "tests/features/a.feature"),
    ("./tests/features/a.feature", "tests/features/a.feature"),
    ("tests/features/a.feature", "tests/features/a.feature"),
])
def test_paths_are_normalised_before_keys_are_computed(raw, clean):
    assert import_service.normalise_path(raw) == clean


@pytest.mark.parametrize("bad", ["", "/etc/a.feature", "C:/a.feature", "a/../b.feature", "x" * 501])
def test_paths_that_are_not_allowed(bad):
    with pytest.raises(ValueError):
        import_service.normalise_path(bad)
