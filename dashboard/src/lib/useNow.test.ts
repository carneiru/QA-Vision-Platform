import { act, renderHook } from "@testing-library/react";
import { useNow } from "./useNow";

test("with null it sets no timer", () => {
  const spy = vi.spyOn(globalThis, "setInterval");
  try {
    renderHook(() => useNow(null));
    expect(spy).not.toHaveBeenCalled();
  } finally {
    spy.mockRestore();
  }
});

test("with an interval it ticks, and clears the timer on unmount", () => {
  vi.useFakeTimers();
  try {
    const { result, unmount } = renderHook(() => useNow(1_000));
    const first = result.current;
    act(() => { vi.advanceTimersByTime(1_000); });
    expect(result.current).toBeGreaterThan(first);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});
