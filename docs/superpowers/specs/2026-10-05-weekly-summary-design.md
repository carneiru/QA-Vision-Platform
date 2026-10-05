# Weekly summary on notification channels

TODO 66 ("scheduled report generation and delivery"). It builds on the Quality Report
(roadmap Phase 3, step 5) and on failure notifications (step 4).

## Scope (this slice)

- Every notification channel (Slack, Teams, webhook, email) can receive a weekly summary
  as well as failure alerts, or instead of them. Each channel has two switches:
  - `on_failure`: on by default, which keeps today's behaviour;
  - `weekly_summary`: off by default.
- The summary covers the previous ISO week, Monday 00:00 to Monday 00:00 UTC. It contains:
  - runs and test executions;
  - pass rate without skipped tests, and the week before's for comparison;
  - failed and errored executions;
  - the five tests that failed most often;
  - a link to the project's Report view.
- A channel's branch filter applies to the summary too: summary of that branch only.
- A week with no runs still sends a short "no runs last week" message. Silence would hide a
  pipeline that stopped uploading.
- Delivery is a job, `python -m src.ingestion.jobs.weekly_summary --loop`, with its own
  compose service, like retention and rollup.
  - On Mondays from `WEEKLY_SUMMARY_HOUR_UTC` (default 7), it sends each due channel the
    previous week once.
  - `last_weekly_week` (for example "2026-W40") records what was sent, so restarts and
    several copies never send twice.
  - A PostgreSQL advisory lock keeps one pass at a time.
  - A failed delivery is recorded like any other delivery (`last_status`/`last_error`) and
    is not retried that week.
- "Send last week's summary" next to "Send test" in Settings → Notifications sends the real
  summary on demand. It does not touch `last_weekly_week`.

## Out of scope

- Per-channel time zones and send days. UTC Monday covers the first users, all in one region.
- PDF attachments. Email stays plain text, and the link opens the printable Report.
- Flaky counts in the summary. Flaky detection needs rollups and windows that do not map to
  a calendar week; the Report shows them.

## Data

Migration 014 adds three columns to `notification_channels`:

- `on_failure`: boolean, not null, default true;
- `weekly_summary`: boolean, not null, default false;
- `last_weekly_week`: varchar(8), null.

The API exposes `on_failure` and `weekly_summary` in create, update and out.
`POST .../test?message=weekly` sends the summary.
