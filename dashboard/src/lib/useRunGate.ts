import { useQuery } from "@tanstack/react-query";
import { getProject } from "../api/orgs";
import { CiTarget, RunRequest, getCiTarget, isActive, listRunRequests, tokenState } from "../api/runRequests";

export const RUN_POLL_MS = 5_000;
// Mirror EDIT_ROLES / the run endpoints in test-management's api/deps.py: who may run and stop, and who manages the target
export const RUN_ROLES = ["owner", "admin", "member"];
export const MANAGE_ROLES = ["owner", "admin"];

export type RunGate = { ok: true; target: CiTarget } | { ok: false; reason: string; toSettings: boolean };

/** The project's newest run request; polled every 5 s while the server still checks it with GitHub. */
export function useLatestRunRequest(projectId: number) {
  return useQuery({
    queryKey: ["run-requests", projectId, "latest"],
    queryFn: async (): Promise<RunRequest | null> => (await listRunRequests(projectId, { limit: 1, offset: 0 })).items[0] ?? null,
    refetchInterval: (query) => (query.state.data?.refreshing ? RUN_POLL_MS : false),
  });
}

export function useCiTarget(projectId: number) {
  return useQuery({ queryKey: ["ci-target", projectId], queryFn: () => getCiTarget(projectId) });
}

/** Whether Play may start a run, and if not the reason to show; first matching reason wins. */
export function gate(role: string | undefined, target: CiTarget, latest: RunRequest | null, now: number = Date.now()): RunGate {
  if (!RUN_ROLES.includes(role ?? "")) return { ok: false, reason: "Viewers can't run tests", toSettings: false };
  if (!target.available) return { ok: false, reason: "Running tests from QEOS is not configured on this server", toSettings: false };
  if (!target.configured) return { ok: false, reason: "Configure in Settings", toSettings: true };
  if (tokenState(target, now) === "expired") return { ok: false, reason: "GitHub token expired", toSettings: true };
  if (latest && isActive(latest)) return { ok: false, reason: "A run is in progress", toSettings: false };
  return { ok: true, target };
}

/** Undefined while the role, the target or the newest request is still loading. */
export function useRunGate(projectId: number): RunGate | undefined {
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId) });
  const target = useCiTarget(projectId);
  const latest = useLatestRunRequest(projectId);
  if (!project.data || !target.data || latest.isPending) return undefined;
  return gate(project.data.my_role, target.data, latest.data ?? null);
}
