import { describe, expect, test } from "vitest";
import { pointsDelta, relativeDelta } from "./reportDelta";

describe("reportDelta", () => {
  test("pass rate moves in points and up is better", () => {
    expect(pointsDelta(0.9781, 0.9661, 30, "up")).toEqual({
      direction: "up",
      text: "up 1.2 pts vs previous 30 days",
      spoken: "up 1.2 points versus the previous 30 days",
      verdict: "better",
    });
    expect(pointsDelta(0.9, 0.95, 7, "up")?.verdict).toBe("worse");
  });

  test("counts and durations move relatively; failures down is better", () => {
    expect(relativeDelta(86, 100, 30, "down")).toEqual({
      direction: "down",
      text: "down 14% vs previous 30 days",
      spoken: "down 14 percent versus the previous 30 days",
      verdict: "better",
    });
    expect(relativeDelta(120, 100, 30, "down")?.verdict).toBe("worse");
  });

  test("runs are neutral, no change is flat, and a start from zero is said in words", () => {
    expect(relativeDelta(412, 398, 30, "neither")?.verdict).toBeNull();
    expect(relativeDelta(100, 100, 30, "down")).toMatchObject({
      direction: "flat",
      text: "no change vs previous 30 days",
      verdict: null,
    });
    expect(relativeDelta(5, 0, 30, "down")).toMatchObject({
      direction: "up",
      text: "up from 0 vs previous 30 days",
      verdict: "worse",
    });
    expect(relativeDelta(0, 0, 30, "down")?.direction).toBe("flat");
  });

  test("no delta without both values", () => {
    expect(pointsDelta(null, 0.9, 30, "up")).toBeNull();
    expect(relativeDelta(3, null, 30, "down")).toBeNull();
  });
});
