import "@testing-library/jest-dom";
import { vi } from "vitest";

// jsdom does not implement scrollIntoView; mock for components that rely on it.
Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
  value: vi.fn(),
  writable: true,
});
