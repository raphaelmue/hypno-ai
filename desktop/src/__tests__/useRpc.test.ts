import { describe, it, expect, vi, beforeEach } from "vitest";
import { rpcCall } from "../hooks/useRpc";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setTauri(invoke: ReturnType<typeof vi.fn> | undefined) {
  if (invoke === undefined) {
    delete (window as unknown as Record<string, unknown>)["__TAURI__"];
  } else {
    (window as unknown as Record<string, unknown>)["__TAURI__"] = {
      core: { invoke },
    };
  }
}

// ---------------------------------------------------------------------------
// rpcCall
// ---------------------------------------------------------------------------

describe("rpcCall", () => {
  beforeEach(() => {
    setTauri(vi.fn().mockResolvedValue({}));
  });

  it("calls window.__TAURI__.core.invoke with the rpc_call command", async () => {
    const mockInvoke = vi.fn().mockResolvedValue({ ok: true });
    setTauri(mockInvoke);

    await rpcCall("script.lint", { path: "/tmp/test.hypno" });

    expect(mockInvoke).toHaveBeenCalledWith("rpc_call", {
      method: "script.lint",
      params: { path: "/tmp/test.hypno" },
    });
  });

  it("returns the value resolved by invoke", async () => {
    const payload = { voices: [{ id: "af", name: "Af" }] };
    setTauri(vi.fn().mockResolvedValue(payload));

    const result = await rpcCall("voices.list", { engine: "kokoro" });
    expect(result).toEqual(payload);
  });

  it("uses an empty params object when none are provided", async () => {
    const mockInvoke = vi.fn().mockResolvedValue({});
    setTauri(mockInvoke);

    await rpcCall("models.status");

    expect(mockInvoke).toHaveBeenCalledWith("rpc_call", {
      method: "models.status",
      params: {},
    });
  });

  it("throws when Tauri is not available", async () => {
    setTauri(undefined);
    await expect(rpcCall("script.lint", {})).rejects.toThrow(
      /Tauri not available/
    );
  });

  it("propagates rejections from invoke", async () => {
    setTauri(vi.fn().mockRejectedValue(new Error("sidecar crashed")));
    await expect(rpcCall("render.start", {})).rejects.toThrow(
      "sidecar crashed"
    );
  });

  it("passes arbitrary params through unchanged", async () => {
    const mockInvoke = vi.fn().mockResolvedValue({});
    setTauri(mockInvoke);

    const params = { engine: "coqui", voice: "speaker1", speed: 0.9 };
    await rpcCall("render.preview", params);

    expect(mockInvoke).toHaveBeenCalledWith("rpc_call", {
      method: "render.preview",
      params,
    });
  });
});
