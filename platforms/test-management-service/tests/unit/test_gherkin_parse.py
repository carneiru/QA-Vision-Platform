"""Gherkin text -> scenarios (ADR-023): keys, rendering, tags, outlines, languages, errors."""
import hashlib
from pathlib import Path

from qeos_shared.keys import test_key as make_test_key
from src.casebook.gherkin_import.parse import parse_feature, source_key

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PATH = "tests/features/checkout.feature"


def parsed(name="checkout.feature", path=PATH):
    return parse_feature(path, (FIXTURES / name).read_text(encoding="utf-8"))


def by_name(result):
    return {s.name: s for s in result.scenarios}


def test_source_key_is_sha256_of_path_and_name():
    assert source_key("a.feature", "x") == hashlib.sha256("a.feature\0x".encode()).hexdigest()


def test_every_scenario_and_outline_becomes_one_case_and_duplicate_names_are_skipped():
    result = parsed()
    assert [s.name for s in result.scenarios] == ["Pay by card", "Tag edge cases", "Apply <code>"]
    assert result.errors == []
    duplicate = [w for w in result.warnings if "Pay by card" in w.message]
    assert len(duplicate) == 1 and duplicate[0].line == 19
    assert duplicate[0].skipped
    assert all(not w.skipped for w in result.warnings if "@bad!tag" in w.message)


def test_gherkin_keeps_backgrounds_tables_and_doc_strings():
    assert by_name(parsed())["Pay by card"].gherkin == (
        "Background:\n"
        "  Given a signed-in shopper\n"
        "Scenario: Pay by card\n"
        "  When I pay with a stored card\n"
        "    | brand | last4 |\n"
        "    | visa | 4242 |\n"
        "  Then the order is confirmed\n"
        '    """json\n'
        '    {"status": "confirmed"}\n'
        '    """'
    )


def test_an_outline_keeps_rule_background_and_examples_in_its_gherkin():
    outline = by_name(parsed())["Apply <code>"]
    assert outline.gherkin == (
        "Background:\n"
        "  Given a signed-in shopper\n"
        '  Given a coupon "SAVE10"\n'
        "Scenario Outline: Apply <code>\n"
        '  When I apply "<code>"\n'
        "  Then the total drops by <off>\n"
        "  Examples:\n"
        "    | code | off |\n"
        "    | SAVE10 | 10 |\n"
        "    | SAVE20 | 20 |"
    )


def test_tags_become_labels_and_priority():
    scenarios = by_name(parsed())
    card = scenarios["Pay by card"]
    assert card.labels == ("ado-81284", "checkout", "smoke")
    assert card.priority == "high"                         # the scenario's tag beats the feature's
    assert scenarios["Apply <code>"].priority == "low"     # inherited from the feature


def test_tags_that_are_still_invalid_are_skipped_with_a_warning():
    result = parsed()
    edge = by_name(result)["Tag edge cases"]
    assert edge.labels == ("checkout", "has-colon")
    assert any("@bad!tag" in w.message for w in result.warnings)


def test_more_than_20_tags_keeps_20_and_warns():
    tags = " ".join(f"@t{i}" for i in range(25))
    result = parse_feature("a.feature", f"Feature: F\n  {tags}\n  Scenario: S\n    Given x\n")
    assert len(result.scenarios[0].labels) == 20
    assert any("20" in w.message for w in result.warnings)


def test_description_title_and_keys():
    card = by_name(parsed())["Pay by card"]
    assert card.description == "The happy path."
    assert card.title == "Pay by card" and card.feature_name == "Checkout"
    assert card.source_key == source_key(PATH, "Pay by card")
    assert card.test_key == make_test_key("Checkout", PATH, "Pay by card")


def test_an_outline_with_placeholders_links_to_its_first_example_row():
    outline = by_name(parsed())["Apply <code>"]
    assert outline.test_name == "Apply SAVE10"
    assert outline.test_key == make_test_key("Checkout", PATH, "Apply SAVE10")


def test_a_long_name_is_cut_for_the_title_but_not_for_the_keys():
    name = "n" * 250
    s = parse_feature("a.feature", f"Feature: F\n  Scenario: {name}\n    Given x\n").scenarios[0]
    assert len(s.title) == 200 and s.name == name
    assert s.source_key == source_key("a.feature", name)


def test_another_language_parses_with_its_own_keywords():
    s = parsed("portugues.feature", "f/pt.feature").scenarios[0]
    assert s.name == "Pagar com cartão" and s.feature_name == "Pagamento"
    assert s.gherkin.splitlines() == ["Cenário: Pagar com cartão", "  Dado um carrinho", "  Quando pago",
                                      "  Então a encomenda é confirmada"]


def test_a_syntax_error_skips_the_file_and_reports_the_line():
    result = parsed("broken.feature", "b.feature")
    assert result.scenarios == []
    assert len(result.errors) == 1 and result.errors[0].line == 4


def test_an_empty_file_or_one_without_a_feature_has_no_scenarios_and_no_error():
    assert parse_feature("e.feature", "").scenarios == []
    assert parse_feature("e.feature", "# only a comment\n").errors == []


def test_a_leading_byte_order_mark_is_ignored():
    plain = "Feature: A\n  Scenario: s\n    Given x\n"
    with_bom = parse_feature("a.feature", "\ufeff" + plain)
    without = parse_feature("a.feature", plain)
    assert with_bom.errors == []
    assert [(s.source_key, s.test_key) for s in with_bom.scenarios] == [(s.source_key, s.test_key) for s in without.scenarios]
    assert with_bom.scenarios[0].feature_name == "A"
