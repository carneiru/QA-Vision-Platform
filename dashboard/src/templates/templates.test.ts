import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import workflowYaml from "./qeos-run.yml.txt?raw";
import runnerScript from "./qeos-run.mjs.txt?raw";

// The dashboard's Docker build sees only dashboard/, so the help block reads these copies; they must
// stay identical to the templates people copy from the repository.
// Relative to this file: dashboard/src/templates -> the repository root. Under vitest import.meta.url can be
// a non-file URL, so fall back to the working directory (vitest runs from dashboard/).
function repoRoot(): string {
  try {
    const here = fileURLToPath(new URL("../../../templates/github/", import.meta.url));
    if (existsSync(here)) return here;
  } catch {
    // not a file: URL
  }
  return resolve(process.cwd(), "..", "templates", "github");
}
const repoFile = (name: string) => readFileSync(resolve(repoRoot(), name), "utf8");

test("the dashboard's copies match templates/github", () => {
  expect(workflowYaml).toBe(repoFile("qeos-run.yml"));
  expect(runnerScript).toBe(repoFile("qeos-run.mjs"));
});
