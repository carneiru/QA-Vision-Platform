import pytest
from pydantic import ValidationError

from src.project.schemas.settings import merge_settings, settings_view


def test_view_fills_every_default():
    assert settings_view({}).model_dump() == {
        "result_retention_days": 90,
        "default_environment": None,
        "notify_on_failure": False,
    }
    assert settings_view(None).result_retention_days == 90


def test_merge_stores_only_explicit_keys():
    assert merge_settings({}, {"notify_on_failure": True}) == {"notify_on_failure": True}


def test_merge_keeps_absent_keys():
    assert merge_settings({"result_retention_days": 30}, {"notify_on_failure": True}) == {
        "result_retention_days": 30,
        "notify_on_failure": True,
    }


def test_null_reverts_a_key_to_its_default():
    assert merge_settings({"result_retention_days": 30}, {"result_retention_days": None}) == {}


def test_values_are_stored_coerced():
    assert merge_settings({}, {"result_retention_days": "30"}) == {"result_retention_days": 30}


def test_unknown_key_is_rejected():
    with pytest.raises(ValueError, match="retention_dayz"):
        merge_settings({}, {"retention_dayz": 5})


@pytest.mark.parametrize(
    "patch",
    [
        {"result_retention_days": 0},
        {"result_retention_days": 366},
        {"default_environment": "x" * 51},
        {"notify_on_failure": "definitely"},
    ],
)
def test_invalid_values_are_rejected(patch):
    with pytest.raises(ValidationError):
        merge_settings({}, patch)


def test_merge_does_not_mutate_the_stored_dict():
    stored = {"result_retention_days": 30}
    merge_settings(stored, {"result_retention_days": 60})
    assert stored == {"result_retention_days": 30}


def test_view_ignores_keys_the_model_no_longer_defines():
    view = settings_view({"legacy_setting": 5, "notify_on_failure": True})
    assert view.notify_on_failure is True
    assert "legacy_setting" not in view.model_dump()


def test_merge_drops_a_stale_key_the_model_no_longer_defines():
    assert merge_settings({"legacy_setting": 5, "result_retention_days": 30}, {"notify_on_failure": True}) == {
        "result_retention_days": 30,
        "notify_on_failure": True,
    }
