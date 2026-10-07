// QEOS: run the scenarios a QEOS Play selected. qeos-run.yml calls this.
// Copy to .github/scripts/qeos-run.mjs in the test repository.
//
// The inputs arrive only through environment variables (QEOS_PATHS, QEOS_NAMES), never through ${{ }}
// inside run:, and cucumber-js is started with an argument array, never through a shell: a scenario
// name is data and can never become a command.
import { spawn } from "node:child_process";
import { appendFileSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

// Arguments go to cucumber-js as an array, never through a shell, so only path traversal,
// control characters and characters a file name cannot hold are refused (OBT has names with + and spaces).
const FEATURE_PATH = /^tests\/features\/[^\u0000-\u001f\\:*?"<>|]+\.feature$/;
const PLACEHOLDER = /<[^<>]+>/g;
const REPORT = "test-results/cucumber-report.json";
const NO_MATCH =
  "No scenario matched this QEOS selection. A scenario was probably renamed or moved since the last " +
  "import: re-import the .feature files in QEOS, then run it again.";

function jsonArrayOfStrings(raw, variable) {
  let value;
  try {
    value = JSON.parse(raw ?? "");
  } catch {
    throw new Error(`${variable} is not JSON`);
  }
  if (!Array.isArray(value) || value.length === 0 || !value.every((item) => typeof item === "string" && item.length > 0)) {
    throw new Error(`${variable} must be a non-empty JSON array of non-empty strings`);
  }
  return value;
}

/** The selected .feature files, once each: only under tests/features, never with "..". */
export function parsePaths(raw) {
  const paths = jsonArrayOfStrings(raw, "QEOS_PATHS");
  for (const path of paths) {
    if (!FEATURE_PATH.test(path) || path.split("/").includes("..")) {
      throw new Error(`path not allowed: ${JSON.stringify(path)}`);
    }
  }
  return [...new Set(paths)];
}

export function parseNames(raw) {
  return jsonArrayOfStrings(raw, "QEOS_NAMES");
}

/** A scenario name as a cucumber-js --name pattern: the whole name, literally, except that each
 *  Scenario Outline <placeholder> matches the example value cucumber-js puts in its place. */
export function namePattern(name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return `^${escaped.replace(PLACEHOLDER, ".*")}$`;
}

export function cucumberArgs(paths, names) {
  return [
    "cucumber-js",
    ...paths,
    ...names.flatMap((name) => ["--name", namePattern(name)]),
    "--profile", "ci",
    "--format", "html:test-results/cucumber-report.html",
    "--parallel", "1",
    "--retry", "0",
  ];
}

/** Scenarios in a cucumber-js JSON report (a Background is not a scenario). */
export function countScenarios(report) {
  if (!Array.isArray(report)) return 0;
  return report.reduce((total, feature) => {
    const elements = Array.isArray(feature?.elements) ? feature.elements : [];
    return total + elements.filter((element) => element?.type !== "background").length;
  }, 0);
}

function run(args) {
  return new Promise((resolve) => {
    const child = spawn("npx", args, { stdio: "inherit", shell: false });
    child.on("error", () => resolve(1));
    child.on("close", (code) => resolve(code ?? 1));
  });
}

async function main() {
  const paths = parsePaths(process.env.QEOS_PATHS);
  const names = parseNames(process.env.QEOS_NAMES);
  const code = await run(cucumberArgs(paths, names));
  let report = [];
  try {
    report = JSON.parse(readFileSync(REPORT, "utf8"));
  } catch {
    // no report: cucumber-js stopped before running anything, and its own output says why
  }
  if (countScenarios(report) === 0) {
    console.log(`::warning title=QEOS::${NO_MATCH}`);
    if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, `### QEOS\n\n${NO_MATCH}\n`);
  }
  process.exitCode = code;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.log(`::error title=QEOS::${error.message}`);
    process.exitCode = 1;
  });
}
