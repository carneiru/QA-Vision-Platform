import { act, render, screen } from "@testing-library/react";
import { useIsWide } from "./useIsWide";

// A ResizeObserver stand-in: the test decides when the browser "measures"
let observers: { cb: ResizeObserverCallback; targets: Element[] }[] = [];
class FakeResizeObserver {
  entry: { cb: ResizeObserverCallback; targets: Element[] };
  constructor(cb: ResizeObserverCallback) {
    this.entry = { cb, targets: [] };
    observers.push(this.entry);
  }
  observe(el: Element) { this.entry.targets.push(el); }
  unobserve() {}
  disconnect() { observers = observers.filter((o) => o !== this.entry); }
}

const real = globalThis.ResizeObserver;
beforeEach(() => {
  observers = [];
  globalThis.ResizeObserver = FakeResizeObserver as unknown as typeof ResizeObserver;
});
afterEach(() => {
  globalThis.ResizeObserver = real;
});

function size(el: HTMLElement, scrollWidth: number, clientWidth: number) {
  Object.defineProperty(el, "scrollWidth", { configurable: true, value: scrollWidth });
  Object.defineProperty(el, "clientWidth", { configurable: true, value: clientWidth });
}
const resize = () => act(() => { for (const o of observers) o.cb([], {} as ResizeObserver); });

function Card() {
  const { ref, wide } = useIsWide<HTMLDivElement>();
  return (
    <div ref={ref} data-testid="card" className={wide ? "card is-wide" : "card"}>
      <table className="data"><tbody><tr><td>x</td></tr></tbody></table>
    </div>
  );
}

test("a table card is wide while its content is wider than the card, and follows resizes", () => {
  render(<Card />);
  const card = screen.getByTestId("card");
  // It watches the card and the table, so new rows and a narrower window are both seen
  expect(observers[0].targets).toEqual([card, card.querySelector("table")]);
  size(card, 1200, 900);
  resize();
  expect(card).toHaveClass("is-wide");
  size(card, 900, 900);
  resize();
  expect(card).not.toHaveClass("is-wide");
});

test("it measures once on mount, before any resize", () => {
  // jsdom lays nothing out: give the card a size before it mounts
  const proto = HTMLDivElement.prototype;
  const sw = Object.getOwnPropertyDescriptor(Element.prototype, "scrollWidth");
  const cw = Object.getOwnPropertyDescriptor(Element.prototype, "clientWidth");
  Object.defineProperty(proto, "scrollWidth", { configurable: true, get: () => 1000 });
  Object.defineProperty(proto, "clientWidth", { configurable: true, get: () => 500 });
  try {
    render(<Card />);
    expect(screen.getByTestId("card")).toHaveClass("is-wide");
  } finally {
    delete (proto as unknown as Record<string, unknown>).scrollWidth;
    delete (proto as unknown as Record<string, unknown>).clientWidth;
    if (sw) Object.defineProperty(Element.prototype, "scrollWidth", sw);
    if (cw) Object.defineProperty(Element.prototype, "clientWidth", cw);
  }
});

test("without ResizeObserver it still measures once and never throws", () => {
  // @ts-expect-error simulate an old browser
  globalThis.ResizeObserver = undefined;
  render(<Card />);
  expect(screen.getByTestId("card")).not.toHaveClass("is-wide");
});
