import { describe, it, expect, vi, beforeEach } from "vitest";
import { rpcCall } from "../hooks/useRpc";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setElectronAPI(
  impl:
    | { rpcCall: ReturnType<typeof vi.fn>; rpcStream: ReturnType<typeof vi.fn> }
    | undefined
) {
  if (impl === undefined) {
    delete (window as unknown as Record<string, unknown>)["electronAPI"];
  } else {
    (window as unknown as Record<string, unknown>)["electronAPI"] = impl;
  }
}

// ---------------------------------------------------------------------------
// rpcCall
// ---------------------------------------------------------------------------

describe("rpcCall", () => {
  beforeEach(() => {
    setElectronAPI({
      rpcCall: vi.fn().mockResolvedValue({}),
      rpcStream: vi.fn().mockResolvedValue(undefined),
    });
  });

  it("calls window.electronAPI.rpcCall with method and params", async () => {
    const mockRpcCall = vi.fn().mockResolvedValue({ ok: true });
    setElectronAPI({ rpcCall: mockRpcCall, rpcStream: vi.fn().mockResolvedValue(undefined) });

    await rpcCall("script.lint", { path: "/tmp/test.hypno" });

    expect(mockRpcCall).toHaveBeenCalledWith("script.lint", {
      path: "/tmp/test.hypno",
    });
  });

  it("returns the value resolved by rpcCall", async () => {
    const payload = { voices: [{ id: "af", name: "Af" }] };
    setElectronAPI({
      rpcCall: vi.fn().mockResolvedValue(payload),
      rpcStream: vi.fn().mockResolvedValue(undefined),
    });

    const result = await rpcCall("voices.list", { engine: "kokoro" });
    expect(result).toEqual(payload);
  });

  it("uses an empty params object when none are provided", async () => {
    const mockRpcCall = vi.fn().mockResolvedValue({});
    setElectronAPI({ rpcCall: mockRpcCall, rpcStream: vi.fn().mockResolvedValue(undefined) });

    await rpcCall("models.status");

    expect(mockRpcCall).toHaveBeenCalledWith("models.status", {});
  });

  it("throws when Electron API is not available", async () => {
    setElectronAPI(undefined);
    await expect(rpcCall("script.lint", {})).rejects.toThrow(
      /Electron API not available/
    );
  });

  it("propagates rejections from rpcCall", async () => {
    setElectronAPI({
      rpcCall: vi.fn().mockRejectedValue(new Error("sidecar crashed")),
      rpcStream: vi.fn().mockResolvedValue(undefined),
    });
    await expect(rpcCall("render.start", {})).rejects.toThrow(
      "sidecar crashed"
    );
  });

  it("passes arbitrary params through unchanged", async () => {
    const mockRpcCall = vi.fn().mockResolvedValue({});
    setElectronAPI({ rpcCall: mockRpcCall, rpcStream: vi.fn().mockResolvedValue(undefined) });

    const params = { engine: "coqui", voice: "speaker1", speed: 0.9 };
    await rpcCall("render.preview", params);

    expect(mockRpcCall).toHaveBeenCalledWith("render.preview", params);
  });
});
