import { StatsRow, getTests } from "../api/analytics";

const EXPORT_PAGE = 200; // the API's max limit for /analytics/tests
const EXPORT_CAP = 10_000;

export async function fetchAllTests(
  projectId: number,
  opts: { days: number; sort: "failures" | "duration" | "name"; search?: string },
): Promise<StatsRow[]> {
  const all: StatsRow[] = [];
  for (let offset = 0; all.length < EXPORT_CAP; offset += EXPORT_PAGE) {
    const page = await getTests(projectId, { ...opts, limit: EXPORT_PAGE, offset });
    all.push(...page);
    if (page.length < EXPORT_PAGE) break;
  }
  return all.slice(0, EXPORT_CAP);
}
