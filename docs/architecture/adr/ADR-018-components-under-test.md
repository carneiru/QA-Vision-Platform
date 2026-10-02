# ADR-018: Capture components-under-test now, correlate later

Status: Accepted (2026-10-02) · Evidence: migration 008, collector `--component`, tests across all three layers

## Context
Cross-repo analysis (Blueprint Phase 6 AI engine; Phase 4 Workspaces) wants
to answer "which product change broke this test". The collector runs in the
QA repo, so its git change data covers test code only — the product build an
E2E suite ran against lives in another repo the platform never sees. Any
future correlation needs to know, per run, which repo versions were deployed
under test. Historical data cannot be reconstructed: what is not captured at
ingest time is lost.

## Decision
Capture the link now, analyse later. An upload may carry up to 20
`{name, sha}` component pairs (collector `--component NAME@SHA`, repeatable,
or `QAV_COMPONENTS`); the ingestion service stores them per run
(`run_components`, CASCADE with the run) and echoes them on the run read
API. No analysis, no new technology, no workspace entity yet — the data lies
dormant until Phase 6's trigger fires. Bad component input is a config error
(exit 2), never silently dropped: it is identity data, and a poisoned
history is worse than a failed upload. Workspaces (grouping QA projects with
product repos) remain a Phase 4 slice behind their trigger.

## Consequences
Every month of CI runs from now on is usable history for failure↔product-commit
correlation. Value depends on pipelines passing the deployed sha — optional,
so sparse data degrades gracefully to "not reported". Deterministic uses
(triage: "product moved from X to Y since the last green run") become possible
before any AI exists.
