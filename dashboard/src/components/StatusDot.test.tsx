import { render } from "@testing-library/react";
import StatusDot from "./StatusDot";

test.each([
  ["passed", "shape-passed"],
  ["failed", "shape-failed"],
  ["errored", "shape-errored"],
  ["skipped", "shape-skipped"],
  ["mystery", "shape-other"],
])("%s has its own shape class, the word, and a decorative dot", (status, shape) => {
  const { container } = render(<StatusDot status={status} />);
  const dot = container.querySelector(".status-dot")!;
  expect(dot).toHaveClass(shape);
  expect(dot).toHaveAttribute("aria-hidden", "true");
  expect(container).toHaveTextContent(status);
});
