import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { EngineManager } from "../components/EngineManager";
import type { CatalogVoice, EngineSpec, ModelStatus } from "../types";

// ---------------------------------------------------------------------------
// Mock the entire useRpc hook so tests never hit Electron
// ---------------------------------------------------------------------------

const mockRpc = {
  modelsStatus: vi.fn<() => Promise<ModelStatus>>(),
  enginesList: vi.fn(),
  voicesCatalog: vi.fn(),
  modelsDownload: vi.fn(),
  modelsDownloadProgress: vi.fn(),
  modelsRemove: vi.fn(),
  enginesInstall: vi.fn(),
  enginesUninstall: vi.fn(),
};

vi.mock("../hooks/useRpc", () => ({
  useRpc: () => mockRpc,
}));

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const STATUS: ModelStatus = {
  gpu_available: false,
  vram_total_mb: 0,
  disk_used_mb: 500,
};

const ENGINES: EngineSpec[] = [
  {
    name: "piper",
    installed: true,
    voice_type: "catalog",
    vram_mb: 0,
    model_size_gb: 0,
    languages: ["en"],
    supports_cloning: false,
    supports_emotions: false,
    emotions: [],
    license: "MIT",
    description: "Lightweight CPU TTS",
  },
  {
    name: "kokoro",
    installed: false,
    voice_type: "preset",
    vram_mb: 2048,
    model_size_gb: 0.3,
    languages: ["en"],
    supports_cloning: false,
    supports_emotions: false,
    emotions: [],
    license: "Apache-2.0",
    description: "High-quality neural TTS",
  },
];

const CATALOG_VOICES: CatalogVoice[] = [
  {
    id: "en_US-amy-medium",
    name: "Amy",
    language: "en_US",
    quality: "medium",
    size_mb: 26,
    installed: true,
  },
  {
    id: "en_US-ryan-high",
    name: "Ryan",
    language: "en_US",
    quality: "high",
    size_mb: 67,
    installed: false,
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EngineManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRpc.modelsStatus.mockResolvedValue(STATUS);
    mockRpc.enginesList.mockResolvedValue({ engines: [] });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: [] });
    mockRpc.modelsDownload.mockResolvedValue({ job_id: "j1", size_mb: 26 });
    mockRpc.modelsRemove.mockResolvedValue({ freed_mb: 26 });
    mockRpc.modelsDownloadProgress.mockResolvedValue({
      state: "downloading",
      progress_pct: 50,
      speed_mbps: 10,
      error: null,
    });
    mockRpc.enginesInstall.mockResolvedValue(undefined);
    mockRpc.enginesUninstall.mockResolvedValue({ uninstalled: true });
  });

  // --- Loading / error states ---

  it("shows loading spinner initially", () => {
    mockRpc.modelsStatus.mockImplementation(() => new Promise(() => {}));
    render(<EngineManager />);
    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });

  it("shows error message when the RPC call fails", async () => {
    mockRpc.modelsStatus.mockRejectedValue(new Error("connection refused"));
    render(<EngineManager />);
    await waitFor(() =>
      expect(screen.getByText(/Failed to load/)).toBeInTheDocument()
    );
  });

  // --- Status bar ---

  it('shows "CPU only" when GPU is not available', async () => {
    render(<EngineManager />);
    await waitFor(() =>
      expect(screen.getByText(/CPU only/)).toBeInTheDocument()
    );
  });

  it("shows GPU info when GPU is available", async () => {
    mockRpc.modelsStatus.mockResolvedValue({
      gpu_available: true,
      vram_total_mb: 8192,
      disk_used_mb: 1200,
    });
    render(<EngineManager />);
    await waitFor(() =>
      expect(screen.getByText(/GPU available/)).toBeInTheDocument()
    );
  });

  // --- TTS Engines section ---

  it("shows all engines with installed status", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    render(<EngineManager />);
    await waitFor(() =>
      expect(screen.getByText("piper")).toBeInTheDocument()
    );
    expect(screen.getByText("kokoro")).toBeInTheDocument();
  });

  it("shows GPU badge for GPU-required engines", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    render(<EngineManager />);
    await waitFor(() =>
      expect(screen.getByText("kokoro")).toBeInTheDocument()
    );
    expect(screen.getByText("GPU")).toBeInTheDocument();
  });

  it("shows Install button for uninstalled engines", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    render(<EngineManager />);
    await waitFor(() => screen.getByText("kokoro"));
    expect(screen.getByRole("button", { name: /install/i })).toBeInTheDocument();
  });

  it("calls enginesInstall when Install is clicked", async () => {
    const user = userEvent.setup();
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /install/i }));
    await user.click(screen.getByRole("button", { name: /install/i }));
    expect(mockRpc.enginesInstall).toHaveBeenCalledWith("kokoro", expect.any(Function));
  });

  it("shows Uninstall button for installed non-piper engines", async () => {
    const installedKokoro: EngineSpec = { ...ENGINES[1], installed: true };
    mockRpc.enginesList.mockResolvedValue({ engines: [ENGINES[0], installedKokoro] });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /uninstall/i }));
  });

  it("calls enginesUninstall after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const installedKokoro: EngineSpec = { ...ENGINES[1], installed: true };
    mockRpc.enginesList.mockResolvedValue({ engines: [ENGINES[0], installedKokoro] });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /uninstall/i }));
    await user.click(screen.getByRole("button", { name: /uninstall/i }));
    expect(mockRpc.enginesUninstall).toHaveBeenCalledWith("kokoro");
  });

  it("does not call enginesUninstall when confirmation is cancelled", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const installedKokoro: EngineSpec = { ...ENGINES[1], installed: true };
    mockRpc.enginesList.mockResolvedValue({ engines: [ENGINES[0], installedKokoro] });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /uninstall/i }));
    await user.click(screen.getByRole("button", { name: /uninstall/i }));
    expect(mockRpc.enginesUninstall).not.toHaveBeenCalled();
  });

  // --- Piper Voice Packs section ---

  it("shows Piper Voice Packs section when piper is installed", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager />);
    await waitFor(() =>
      expect(screen.getByText("Piper Voice Packs")).toBeInTheDocument()
    );
  });

  it("shows installed voice pack with Remove button", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager />);
    await waitFor(() => screen.getByText("en_US-amy-medium"));
    expect(screen.getByRole("button", { name: /remove/i })).toBeInTheDocument();
  });

  it("shows available voice pack with Download button", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager />);
    await waitFor(() => screen.getByText("en_US-ryan-high"));
    expect(screen.getByRole("button", { name: /download/i })).toBeInTheDocument();
  });

  it("calls modelsDownload when Download voice is clicked", async () => {
    const user = userEvent.setup();
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /download/i }));
    await user.click(screen.getByRole("button", { name: /download/i }));
    expect(mockRpc.modelsDownload).toHaveBeenCalledWith("en_US-ryan-high");
  });

  it("calls modelsRemove after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /remove/i }));
    await user.click(screen.getByRole("button", { name: /remove/i }));
    expect(mockRpc.modelsRemove).toHaveBeenCalledWith("en_US-amy-medium");
  });

  it("does not call modelsRemove when confirmation is cancelled", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager />);
    await waitFor(() => screen.getByRole("button", { name: /remove/i }));
    await user.click(screen.getByRole("button", { name: /remove/i }));
    expect(mockRpc.modelsRemove).not.toHaveBeenCalled();
  });

  // --- First-launch mode ---

  it("shows first-launch header when isFirstLaunch=true", async () => {
    render(<EngineManager isFirstLaunch={true} />);
    await waitFor(() =>
      expect(screen.getByText(/Welcome to HypnoAI/)).toBeInTheDocument()
    );
  });

  it("'Get Started' button is disabled when no engine is ready", async () => {
    // piper installed but no voice packs, no other engines
    mockRpc.enginesList.mockResolvedValue({ engines: [ENGINES[0]] });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: [] });
    render(<EngineManager isFirstLaunch={true} onClose={vi.fn()} />);
    await waitFor(() => screen.getByRole("button", { name: /Get Started/ }));
    expect(screen.getByRole("button", { name: /Get Started/ })).toBeDisabled();
  });

  it("'Get Started' button is enabled when a Piper voice is installed", async () => {
    mockRpc.enginesList.mockResolvedValue({ engines: ENGINES });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: CATALOG_VOICES });
    render(<EngineManager isFirstLaunch={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Get Started/ })
      ).not.toBeDisabled()
    );
  });

  it("'Get Started' button is enabled when a non-piper engine is installed", async () => {
    const installedKokoro: EngineSpec = { ...ENGINES[1], installed: true };
    mockRpc.enginesList.mockResolvedValue({ engines: [ENGINES[0], installedKokoro] });
    mockRpc.voicesCatalog.mockResolvedValue({ voices: [] });
    render(<EngineManager isFirstLaunch={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Get Started/ })
      ).not.toBeDisabled()
    );
  });
});
