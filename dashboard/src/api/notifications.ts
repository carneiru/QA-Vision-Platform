import { apiFetch } from "./http";

// Mirrors platforms/ingestion-service/src/ingestion/schemas/notification.py

export type ChannelKind = "slack" | "teams" | "webhook" | "email";

export interface NotificationChannel {
  id: number;
  name: string;
  kind: ChannelKind;
  /** A webhook URL's host and last 4 characters (the URL is never returned), or the email addresses. */
  target: string;
  branch: string | null;
  enabled: boolean;
  /** Failed runs as they arrive. */
  on_failure: boolean;
  /** Last week's numbers every Monday. */
  weekly_summary: boolean;
  last_status: "delivered" | "failed" | null;
  last_error: string | null;
  last_sent_at: string | null;
}

const base = (projectId: number) => `/api/v1/projects/${projectId}/notification-channels`;

export function listChannels(projectId: number): Promise<NotificationChannel[]> {
  return apiFetch(base(projectId));
}

export function addChannel(
  projectId: number,
  body: { name: string; kind: ChannelKind; url: string; branch?: string; on_failure: boolean; weekly_summary: boolean },
): Promise<NotificationChannel> {
  return apiFetch(base(projectId), { method: "POST", body: JSON.stringify(body) });
}

export function updateChannel(
  projectId: number,
  channelId: number,
  changes: Partial<Pick<NotificationChannel, "name" | "enabled" | "branch" | "on_failure" | "weekly_summary">>,
): Promise<NotificationChannel> {
  return apiFetch(`${base(projectId)}/${channelId}`, { method: "PATCH", body: JSON.stringify(changes) });
}

/** "test" sends a sample message; "weekly" sends last week's real summary now. */
export function testChannel(
  projectId: number,
  channelId: number,
  message: "test" | "weekly" = "test",
): Promise<{ status: string; error: string | null }> {
  const q = message === "weekly" ? "?message=weekly" : "";
  return apiFetch(`${base(projectId)}/${channelId}/test${q}`, { method: "POST", body: "{}" });
}

export function removeChannel(projectId: number, channelId: number): Promise<void> {
  return apiFetch(`${base(projectId)}/${channelId}`, { method: "DELETE" });
}
