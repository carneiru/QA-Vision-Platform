import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import workflowYaml from "./qa-vision-run.yml.txt?raw";
import runnerScript from "./qa-vision-run.mjs.txt?raw";

// The dashboard's Docker build sees only dashboard/, so the help block reads these copies; they must
// stay identical to the templates people copy from the repository.
const repoFile = (name: string) =>
  readFileSync(resolve(process.cwd(), "..", "templates", "github", name), "utf8"); // vitest runs from dashboard/

test("the dashboard's copies match templates/github", () => {
  expect(workflowYaml).toBe(repoFile("qa-vision-run.yml"));
  expect(runnerScript).toBe(repoFile("qa-vision-run.mjs"));
});
