import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "@/test/server";

// jsdom lacks ResizeObserver (needed by Recharts' ResponsiveContainer) and
// matchMedia — polyfill them so chart-containing components render in tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// jsdom has no EventSource; a quiet stub lets stream-subscribing pages mount.
// Tests that need frames drive components with props instead of the socket.
class EventSourceStub {
  onopen: ((ev: Event) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  constructor(public url: string) {}
  close() {}
}
if (!("EventSource" in globalThis)) {
  globalThis.EventSource = EventSourceStub as unknown as typeof EventSource;
}

// Start the MSW request-mocking server for the whole test run so components/pages
// can be tested against a realistic API without a live backend.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
