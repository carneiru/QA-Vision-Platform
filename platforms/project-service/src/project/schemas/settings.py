from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectSettings(BaseModel):
    # unknown keys are rejected so a typo surfaces instead of being silently stored
    model_config = ConfigDict(extra="forbid")

    result_retention_days: int = Field(90, ge=1, le=365)
    default_environment: Optional[str] = Field(None, max_length=50)
    notify_on_failure: bool = False


def settings_view(stored: Optional[dict]) -> ProjectSettings:
    """The full settings, with defaults for every key that was never set.

    Reads must never 500 over stored data they don't recognize: a setting removed in a later
    version, or a manual DB edit, can leave an unknown key sitting in a row. Drop anything the
    model no longer defines before validating -- `merge_settings` (the write/PATCH path) stays
    strict and still rejects unknown keys with a 422.
    """
    known = {key: value for key, value in (stored or {}).items() if key in ProjectSettings.model_fields}
    return ProjectSettings.model_validate(known)


def merge_settings(stored: Optional[dict], patch: dict) -> dict:
    """Merge-patch: present keys replace, null removes (reverting to the default), absent keys stay.

    Returns a new dict holding only explicitly-set keys, with their validated values, so adding a
    setting with a default later needs no data migration.
    """
    unknown = set(patch) - set(ProjectSettings.model_fields)
    if unknown:
        raise ValueError(f"Unknown setting(s): {', '.join(sorted(unknown))}")

    merged = dict(stored or {})
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value

    validated = ProjectSettings.model_validate(merged)
    return {key: getattr(validated, key) for key in merged}
