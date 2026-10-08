import { viewTitle } from "./viewTitle";

test("the feature page is titled Feature, not as a case number", () => {
  expect(viewTitle("cases/feature")).toBe("Feature");
  expect(viewTitle("cases/12")).toBe("TC-12");
  expect(viewTitle("cases/import")).toBe("Import from Gherkin");
});
