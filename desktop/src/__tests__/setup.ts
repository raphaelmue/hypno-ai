import "@testing-library/jest-dom/vitest";
import { vi, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(cleanup);

// Provide a default Electron API mock so the useRpc hook doesn't throw during
// component initialisation. Individual tests override rpcCall/rpcStream as needed.
(window as unknown as Record<string, unknown>)["electronAPI"] = {
  rpcCall: vi.fn().mockResolvedValue({}),
  rpcStream: vi.fn().mockResolvedValue(undefined),
};
