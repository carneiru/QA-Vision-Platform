# ADR-020: Per-project masking patterns run on RE2, not Python's `re`

Status: Accepted (2026-10-05) · Evidence: ingestion `utils/custom_masking.py`, `test_custom_masking.py` ((a+)+$ on 50 KB in under a second)

## Context
Built-in masking (ADR-014) cannot know a project's own sensitive values: customer numbers,
internal ticket ids, account formats. Projects need their own patterns, which means regular
expressions written by users and run on every uploaded result. Python's `re` backtracks: a
pattern such as `(a+)+$` takes exponential time on crafted or merely unlucky text, and one
such pattern would stall ingestion for every project on the instance. The built-in rules
avoid this by construction (bounded, non-nested quantifiers); user patterns cannot be held
to that by review.

## Decision
Store patterns per project in ingestion-service (`masking_patterns`, at most 20 per project,
256 characters each, name `[a-z][a-z0-9_]{0,31}` shown in the marker) and compile them with
RE2 (`google-re2`), whose matching time is linear in the input. A pattern is refused with a
reason when it does not compile under RE2 or matches empty text. Custom patterns run after
the built-in rules and never inside an existing `[REDACTED:…]` marker. The same masking runs
at ingest, in the re-mask command, and in the preview endpoint, so a preview shows exactly
what would be stored. Metrics count custom matches under one `custom` label: project-chosen
names would make the label set unbounded.

## Consequences
No pattern can stall ingestion. RE2 has no backreferences or lookarounds; the UI says so.
One native dependency (manylinux and Windows wheels exist). Patterns apply to results
sent after they are added; earlier results need `python -m src.ingestion.jobs.remask`.
