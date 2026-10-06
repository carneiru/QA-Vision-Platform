# Test cases: a "Last runs" column (Testim-style strip)

On 2026-10-06 the user asked for a column showing each case's last 10 run results as small coloured
bars, as in Testim. They approved this design.

## What the column shows

The Cases list gets a **Last runs** column after Title. It holds one strip per row: 10 bars, one per
run, oldest on the left and newest on the right.

| Bar | Meaning |
|---|---|
| Green | The case's automated test passed in that run (last attempt passed, single attempt). |
| Red | It failed or errored (last attempt failed or errored). |
| Yellow ("re-run") | The test had more than one attempt in that run. Ingestion stores a retry as another result row with the same `test_key` in the same run, and the run-compare code treats "later rows win". |
| Empty, outline only | The test was not in that run. |

- **The runs are the project's last 10 runs, aligned across rows,** by `started_at` descending with
  ties broken by run id. Every row's bar *n* refers to the same run, so a column can be read down the
  page.
- **Branch:** if the Cases page later gets a branch filter, the strip follows it. Until then it covers
  all branches.
- **Fewer than 10 runs:** the strip shows only the runs that exist.
- **No link:** a case without an `automated_test_key` shows an empty strip with the muted text "not
  linked".

## ingestion: `POST /api/v1/projects/{id}/analytics/run-strip`

- **Body:** `{"test_keys": [...], "limit": 10, "branch": null}`.
  - `test_keys`: 1–200 keys, each 64 hex characters.
  - `limit`: 1–20, default 10.
  - `branch`: optional, at most 255 characters, no NUL.
- **Response:**

  ```json
  {
    "runs": [{"id": 433, "started_at": "...", "branch": "main"}],
    "statuses": {"<key>": ["passed", null, "rerun", "failed", ...]}
  }
  ```

  - `runs` is sorted oldest to newest, up to `limit` entries.
  - Each list in `statuses` lines up with `runs`.
  - Each status is `passed`, `failed` (failed or errored), `rerun`, `skipped`, or `null` when the test
    was not in that run.
  - A skipped test shows as an empty bar with a dashed outline, so it is told apart from "not in
    run".
  - Every requested key appears in `statuses`.
- **Status rules:**
  - More than one result row for the key in the run gives `rerun`, whatever the last outcome.
  - Otherwise the status comes from the single row.
- **Roles:** every project role can read. The route sits under `/analytics/`, which the gateway
  already routes.
- **Cost:** one query for the run ids (`test_runs`, project, optional branch, order and limit), then
  one grouped query over `test_results` for `run_id IN (…)` and `test_key IN (…)`. The page has at
  most 200 keys and 10 runs.

## Dashboard

- **`components/RunStrip.tsx`** takes `{ runs, statuses: (Status | null)[], projectId }`.
  - Bars are 6×18px with a 2px gap, non-interactive spans with hover tooltips ("Run #433, 6 Oct 14:02: failed").
  - Colours: `--status-passed`, `--status-failed`, and a new `--status-rerun` (amber) with light and
    dark values. Each bar has at least 3:1 non-text contrast against the cell background in both
    themes.
  - **Colour is never the only signal.** A failed bar has a notch cut into its top (WCAG 2.5.8). A re-run bar has
    diagonal stripes. A skipped bar has a dashed outline. A "not in run" bar has a solid hairline
    outline and no fill.
  - The strip is one link (minimum 24px tall) to the newest run's detail page, labelled
    "Last 10 runs: 7 passed, 2 failed, 1 re-run" (counting non-zero kinds, including not-run and
    skipped). A visually-hidden ordered list of all runs and their statuses follows the link for
    screen readers. With no results, the strip has `role="img"` (WCAG 2.5.8).
  - Bars don't animate, so there's nothing to change for `prefers-reduced-motion`.
- **Cases page:** once the page of cases has loaded, it collects the linked keys and calls `run-strip`.
  - The query key is `["run-strip", id, keys]`.
  - Until the strip data arrives, the column shows a skeleton of 10 grey bars.
  - If the call fails, the column shows a dash, the rest of the page keeps working, and nothing
    blocks.
  - The column is `hide-narrow`, so it is hidden at 640px and below.
- **Legend:** a small legend next to the table header explains the colours and shapes. It is
  visible text, not only a tooltip.

## Testing

- **ingestion (pytest):**
  - alignment across keys (the same runs for every key);
  - `null` for a test that was not in a run;
  - `rerun` for repeated rows;
  - errored counts as failed;
  - `skipped`;
  - fewer runs than `limit`;
  - the `branch` filter;
  - project isolation;
  - a 422 for 201 keys or a bad key.
- **dashboard (vitest):**
  - RunStrip: each status's class and shape, the group label summary, and the per-bar label and link.
  - Cases page: the column renders with the strip data; a case with no link shows "not linked"; a
    failing `run-strip` call shows a dash and the list still works.
- **Gateway smoke:** `run-strip` through the gateway returns 200.

## Out of scope

- Per-test history beyond 10 runs. The case page already has a test history.
- Choosing a branch for the strip before the Cases page has a branch filter.
