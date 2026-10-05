# Failure notifications: design

Roadmap Phase 3, step 4 ("Notification service"; exit criterion: "Notification system delivering
alerts via email and Slack"). TODO v2 backlog C: "Failure notifications to Slack/Teams/email".

## Scope (this slice)

A project can have **notification channels**. When a run with failed or errored tests is
stored, each enabled channel whose branch filter matches gets a message. The message carries the
counts, the branch and commit, the first failing tests, and a link to the run.

Channel kinds:

| Kind | Target | Payload |
|---|---|---|
| `slack` | Slack incoming webhook, `https://hooks.slack.com/services/…` | `{"text": …, "blocks": […]}` |
| `teams` | Microsoft Teams "Workflows" webhook (Power Automate), `https://*.logic.azure.com/…` or `https://*.powerplatform.com/…`. Office 365 connectors are retired | `{"type": "message", "attachments": [Adaptive Card 1.4]}` |
| `webhook` | any public `https://` URL | JSON run summary (`event: "run.failed"`) |

Email is **out of this slice**. The ingestion service has no SMTP settings, and duplicating auth's
would split the configuration. Email follows once there is a shared mail sender. The roadmap's
exit criterion stays open on email until then.

## Decisions

- **Where it runs.** It runs in ingestion-service, which owns runs. It is not a new service: the
  blueprint has no notification-service, and its event backbone (Kafka) waits for its adoption
  trigger. Delivery is a FastAPI background task after the collect response is sent. The upload's
  transaction is committed, and no database session is held during the HTTP call (the
  "session released before outbound HTTP" rule). The collector's latency is unaffected.
- **No retry queue.** There is no queue or Redis until its trigger fires. One attempt per message
  with a 5-second timeout. The outcome is recorded on the channel (`last_status`, `last_error`,
  `last_sent_at`) and shown in Settings, so a broken webhook is visible rather than silent.
- **When it fires.** Only for a newly created run (an idempotent replay sends nothing), and only if
  `failed + errored > 0`. An optional per-channel `branch` filter is an exact match (for example
  `main`), so pull-request noise can be left out.
- **SSRF.** The server POSTs to user-supplied URLs, so:
  - `slack` and `teams` URLs must be on their vendor hosts;
  - `webhook` must be `https`, on port 443 or no port, without credentials;
  - at send time every resolved address must be public: no loopback, private, link-local, CGNAT,
    multicast or reserved ranges, which covers the Docker network and cloud metadata;
  - redirects are never followed.

  Residual risk: DNS rebinding between the check and the connect. This is acceptable for now:
  redirects are off, and the response body is never read back to the user.
- **Secrets.** Webhook URLs are bearer secrets. They are stored in plaintext, because delivery
  needs them and there is no key management (Vault is TARGET). The API never returns them: it
  shows the host and the last 4 characters. Replacing a URL means deleting the channel and
  adding a new one.
- **Content.** Masked text only: result messages are already masked when stored. A message lists
  at most 5 failing tests. The link uses `DASHBOARD_URL`
  (`{DASHBOARD_URL}/projects/{id}/runs/{run_id}`); compose sets it from the same public origin as
  auth's `BASE_URL`. Without it, the message has no link.
- **Roles.** Owners, admins and members manage channels and send a test message. Viewers see the
  list (masked).
- **Limits.** At most 10 channels per project.

## API (ingestion-service)

- `GET /projects/{id}/notification-channels`
- `POST /projects/{id}/notification-channels` with `{name, kind, url, branch?}`. Answers 422 with
  a reason when the URL is not allowed.
- `PATCH /projects/{id}/notification-channels/{cid}` with `{enabled?, branch?, name?}`
- `DELETE /projects/{id}/notification-channels/{cid}`
- `POST /projects/{id}/notification-channels/{cid}/test` sends a sample message synchronously and
  returns `{status, error}`.

## Dashboard

A Settings card, "Notifications": the list (kind, name, masked target, branch, last delivery in
words), an add form, enable/disable, "Send test", and remove with an in-place confirm.
