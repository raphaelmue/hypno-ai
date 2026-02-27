import "@testing-library/jest-dom/vitest";
import { vi, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(cleanup);

// Provide a default Tauri mock so the useRpc hook doesn't throw during
// component initialisation. Individual tests override invoke as needed.
(window as unknown as Record<string, unknown>)["__TAURI__"] = {
  core: {
    invoke: vi.fn().mockResolvedValue({}),
  },
};
