import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { countScenarios, cucumberArgs, namePattern, parseNames, parsePaths } from "./qa-vision-run.mjs";

const matches = (name, actual) => new RegExp(namePattern(name)).test(actual);

test("regex characters, quotes and dollars in a name match only that name", () => {
  const name = `Pay with a "voucher" (50% off) $5 [promo] *now*? a+b|c \ d. ^x {2} it's`;
  assert.ok(matches(name, name));
  assert.ok(!matches(name, `${name} again`));
  assert.ok(!matches(name, `X${name}`));
  assert.ok(!matches("Pay.by card", "Pay by card"));
  assert.ok(!matches("a+b", "aab"));
});

test("an outline's placeholders match the example values cucumber-js puts in", () => {
  assert.equal(namePattern("Book <city> flight"), "^Book .* flight$");
  assert.ok(matches("Book <city> flight", "Book Rome flight"));
  assert.ok(!matches("Book <city> flight", "Book Rome train"));
  assert.ok(matches("<carrier> flights are flagged as eligible for the traveler's unused ticket",
    "TAP Air Portugal (TP) flights are flagged as eligible for the traveler's unused ticket"));
  assert.ok(matches("Price <a.b> (<x|y>)", "Price 1.5 (yes)"));
});

test("paths must be .feature files under tests/features, never with ..", () => {
  assert.deepEqual(
    parsePaths('["tests/features/a.feature","tests/features/a.feature","tests/features/b c.feature","tests/features/x_+_y (1).feature"]'),
    ["tests/features/a.feature", "tests/features/b c.feature", "tests/features/x_+_y (1).feature"],
  );
  for (const bad of ['["../x.feature"]', '["tests/features/../../etc/x.feature"]', '["tests/features/a.js"]',
    '["tests/features/a.feature; rm -rf /"]', '["tests/features/a\b.feature"]', '["tests/features/a\nb.feature"]', '"tests/features/a.feature"',
    "[]", "not json", undefined]) {
    assert.throws(() => parsePaths(bad), undefined, String(bad));
  }
});

test("names must be a non-empty JSON array of non-empty strings", () => {
  assert.deepEqual(parseNames('["a", "b <c>"]'), ["a", "b <c>"]);
  for (const bad of ["[]", '[""]', "[1]", '{"a":1}', "nope", undefined]) assert.throws(() => parseNames(bad));
});

test("cucumber-js gets one --name per scenario as an argument array, with workers 1 and retries 0", () => {
  assert.deepEqual(cucumberArgs(["tests/features/a.feature"], ['say "hi"', "x"]), [
    "cucumber-js", "tests/features/a.feature", "--name", '^say "hi"$', "--name", "^x$",
    "--profile", "ci", "--format", "html:test-results/cucumber-report.html", "--parallel", "1", "--retry", "0",
  ]);
});

test("scenarios are counted from the cucumber JSON report, backgrounds left out", () => {
  assert.equal(countScenarios([{ elements: [{ type: "background" }, { type: "scenario" }] }, { elements: [{ type: "scenario" }] }]), 2);
  assert.equal(countScenarios([]), 0);
  assert.equal(countScenarios({}), 0);
});

const workflow = readFileSync(fileURLToPath(new URL("./qa-vision-run.yml", import.meta.url)), "utf8");

test("the workflow allows a long suite: timeout-minutes 200", () => {
  assert.match(workflow, /^ {4}timeout-minutes: 200$/m);
});

test("the upload step runs after a failure, but only when QAV_URL is set", () => {
  const step = workflow.split("- name: Upload results to QA Vision")[1].split("- name:")[0];
  assert.match(step, /^ {8}if: always\(\) && vars\.QAV_URL != ''$/m);
});

test("the header says the files must also exist on the configured branch", () => {
  assert.match(workflow, /configured branch/i);
});
