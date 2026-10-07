import { FormEvent, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, CircleDashed, PauseCircle } from "lucide-react";
import {
  ChannelKind,
  NotificationChannel,
  addChannel,
  listChannels,
  removeChannel,
  testChannel,
  updateChannel,
} from "../api/notifications";
import ConfirmButton from "./ConfirmButton";
import ErrorBanner from "./ErrorBanner";

const KINDS: Record<ChannelKind, { label: string; hint: string }> = {
  slack: {
    label: "Slack",
    hint: "An incoming webhook: Slack app → Incoming Webhooks → Add New Webhook to Workspace. Starts with https://hooks.slack.com/.",
  },
  teams: {
    label: "Microsoft Teams",
    hint: "A Workflows webhook: in the channel, … → Workflows → \"Post to a channel when a webhook request is received\", then copy its URL. Office 365 connectors are retired.",
  },
  webhook: {
    label: "Webhook",
    hint: "Any public https:// address; it receives JSON: event \"run.failed\" for failed runs, \"weekly.summary\" for the summary.",
  },
  email: {
    label: "Email",
    hint: "Up to 5 addresses, separated by commas. Sending needs SMTP configured on this server by the administrator; without it, Send test says so.",
  },
};

function LastDelivery({ c }: { c: NotificationChannel }) {
  if (!c.enabled) {
    return <span className="badge badge-muted"><PauseCircle size={14} aria-hidden="true" /> Paused</span>;
  }
  if (c.last_status === "delivered") {
    return <span className="badge badge-passed"><CheckCircle2 size={14} aria-hidden="true" /> Delivered</span>;
  }
  if (c.last_status === "failed") {
    return (
      <span className="badge badge-warn delivery-error">
        <CircleAlert size={14} aria-hidden="true" /> Failed: {c.last_error ?? "unknown error"}
      </span>
    );
  }
  return <span className="badge badge-muted"><CircleDashed size={14} aria-hidden="true" /> Nothing sent yet</span>;
}

interface Props {
  projectId: number;
  projectName: string;
  /** Undefined while the role is loading: the list shows, the controls wait. */
  canEdit: boolean | undefined;
}

export default function NotificationsCard({ projectId, projectName, canEdit }: Props) {
  const qc = useQueryClient();
  const queryKey = ["notification-channels", projectId];
  const [kind, setKind] = useState<ChannelKind>("slack");
  const [name, setName] = useState(projectName);
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [onFailure, setOnFailure] = useState(true);
  const [weekly, setWeekly] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const hintId = useId();

  const channels = useQuery({ queryKey, queryFn: () => listChannels(projectId) });
  const refresh = () => qc.invalidateQueries({ queryKey });

  const add = useMutation({
    mutationFn: () =>
      addChannel(projectId, {
        name: name.trim(), kind, url: url.trim(), ...(branch.trim() ? { branch: branch.trim() } : {}),
        on_failure: onFailure, weekly_summary: weekly,
      }),
    onSuccess: () => {
      setUrl("");
      setBranch("");
      return refresh();
    },
  });
  const toggle = useMutation({
    mutationFn: (c: NotificationChannel) => updateChannel(projectId, c.id, { enabled: !c.enabled }),
    onSuccess: refresh,
  });
  const sends = useMutation({
    mutationFn: ({ c, changes }: { c: NotificationChannel; changes: { on_failure?: boolean; weekly_summary?: boolean } }) =>
      updateChannel(projectId, c.id, changes),
    onSuccess: refresh,
  });
  const test = useMutation({
    mutationFn: ({ c, message }: { c: NotificationChannel; message: "test" | "weekly" }) =>
      testChannel(projectId, c.id, message).then((r) => ({ c, r, message })),
    onSuccess: ({ c, r, message }) => {
      const what = message === "weekly" ? "Last week's summary" : "Test";
      setTestResult(
        r.status === "delivered"
          ? `${what} to ${c.name} delivered.`
          : `${what} to ${c.name} failed: ${r.error ?? "unknown error"}`,
      );
      return refresh();
    },
  });
  const remove = useMutation({ mutationFn: (id: number) => removeChannel(projectId, id), onSuccess: refresh });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  return (
    <div className="card">
      <h3>Notifications</h3>
      <p className="muted">
        Each channel can get <strong>failed runs</strong> as they arrive (counts, the first failing tests and a
        link to the run) and a <strong>weekly summary</strong> on Mondays at 07:00 UTC (last week's pass rate,
        failures and most-failing tests, with a link to the report). Messages carry masked text only.
      </p>

      {channels.error != null && <ErrorBanner error={channels.error} onRetry={() => channels.refetch()} />}
      {channels.isPending && <p className="muted">Loading channels…</p>}
      {channels.data?.length === 0 && <p className="muted">No channels yet.</p>}
      {channels.data != null && channels.data.length > 0 && (
        <table className="data notify-table stacked">
          <thead>
            <tr>
              <th>Channel</th>
              <th className="hide-narrow">Sends to</th>
              <th>Branch</th>
              <th>Sends</th>
              <th>Last delivery</th>
              {canEdit && <th><span className="sr-only">Actions</span></th>}
            </tr>
          </thead>
          <tbody>
            {channels.data.map((c) => (
              <tr key={c.id}>
                <td className="channel-cell">
                  <strong>{c.name}</strong>
                  <div className="muted">{KINDS[c.kind]?.label ?? c.kind}</div>
                </td>
                <td className="hide-narrow wrap-anywhere" data-label="Sends to"><code>{c.target}</code></td>
                <td data-label="Branch">{c.branch ? <code>{c.branch}</code> : <span className="muted">All branches</span>}</td>
                <td className="sends-cell" data-label="Sends">
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={c.on_failure}
                      disabled={!canEdit || sends.isPending}
                      aria-label={`Send failed runs to ${c.name}`}
                      onChange={() => sends.mutate({ c, changes: { on_failure: !c.on_failure } })}
                    />
                    <span aria-hidden="true">Failed runs</span>
                  </label>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={c.weekly_summary}
                      disabled={!canEdit || sends.isPending}
                      aria-label={`Send the weekly summary to ${c.name}`}
                      onChange={() => sends.mutate({ c, changes: { weekly_summary: !c.weekly_summary } })}
                    />
                    <span aria-hidden="true">Weekly summary</span>
                  </label>
                </td>
                <td data-label="Last delivery"><LastDelivery c={c} /></td>
                {canEdit && (
                  <td className="row-actions">
                    <div>
                    <button
                      aria-label={`Send a test message to ${c.name}`}
                      onClick={() => test.mutate({ c, message: "test" })}
                      disabled={test.isPending}
                    >
                      {test.isPending && test.variables?.c.id === c.id && test.variables.message === "test" ? "Sending…" : "Send test"}
                    </button>
                    {c.weekly_summary && (
                      <button
                        aria-label={`Send last week's summary to ${c.name}`}
                        onClick={() => test.mutate({ c, message: "weekly" })}
                        disabled={test.isPending}
                      >
                        {test.isPending && test.variables?.c.id === c.id && test.variables.message === "weekly" ? "Sending…" : "Send summary"}
                      </button>
                    )}
                    <button
                      aria-label={`${c.enabled ? "Pause" : "Resume"} ${c.name}`}
                      onClick={() => toggle.mutate(c)}
                      disabled={toggle.isPending}
                    >
                      {c.enabled ? "Pause" : "Resume"}
                    </button>
                    <ConfirmButton
                      label="Remove"
                      ariaLabel={`Remove ${c.name}`}
                      question={`Remove ${c.name}? Nothing more is posted there.`}
                      confirmLabel="Remove"
                      onConfirm={() => remove.mutate(c.id)}
                      disabled={remove.isPending}
                    />
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {testResult && <p role="status" className="muted">{testResult}</p>}
      {test.error != null && <ErrorBanner error={test.error} />}
      {toggle.error != null && <ErrorBanner error={toggle.error} />}
      {sends.error != null && <ErrorBanner error={sends.error} />}
      {remove.error != null && <ErrorBanner error={remove.error} />}

      {canEdit === false && <p className="muted">Only owners, admins and members can change notifications.</p>}
      {canEdit && (
        <form className="form-stack masking-form" onSubmit={onSubmit}>
          <h4>Add a channel</h4>
          <label>
            Send to
            <select value={kind} onChange={(e) => setKind(e.target.value as ChannelKind)}>
              {Object.entries(KINDS).map(([value, k]) => (
                <option key={value} value={value}>{k.label}</option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            {kind === "email" ? "Email addresses" : "Webhook URL"}
            <input
              required
              type={kind === "email" ? "email" : "url"}
              multiple={kind === "email"}
              autoComplete="off"
              spellCheck={false}
              aria-describedby={hintId}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <span id={hintId} className="muted field-hint">
              {KINDS[kind].hint}
              {kind !== "email" && " Treat it like a password: once saved, only its host and last characters are shown."}
            </span>
          </label>
          <label>
            <span>
              Only branch <span className="muted">(optional)</span>
            </span>
            <input
              maxLength={255}
              autoComplete="off"
              spellCheck={false}
              placeholder="e.g. main; empty means every branch"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
            />
          </label>
          <fieldset className="check-group">
            <legend>Send</legend>
            <label className="check">
              <input type="checkbox" checked={onFailure} onChange={(e) => setOnFailure(e.target.checked)} />
              Failed runs
            </label>
            <label className="check">
              <input type="checkbox" checked={weekly} onChange={(e) => setWeekly(e.target.checked)} />
              Weekly summary <span className="muted">(Mondays, 07:00 UTC)</span>
            </label>
          </fieldset>
          {add.error != null && <ErrorBanner error={add.error} />}
          <div className="button-row">
            <button type="submit" disabled={add.isPending}>
              {add.isPending ? "Adding…" : "Add channel"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
