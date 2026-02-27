import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ModelManager } from "../components/ModelManager";
import type { InstalledModel, AvailableModel, ModelStatus } from "../types";

// ---------------------------------------------------------------------------
// Mock the entire useRpc hook so tests never hit Tauri
// ---------------------------------------------------------------------------

const mockRpc = {
  modelsStatus: vi.fn<() => Promise<ModelStatus>>(),
  modelsList: vi.fn(),
  modelsDownload: vi.fn(),
  modelsDownloadProgress: vi.fn(),
  modelsRemove: vi.fn(),
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

const INSTALLED: InstalledModel[] = [
  {
    name: "en_US-amy-medium",
    type: "voice",
    engine: "piper",
    size_mb: 26,
    loaded: false,
    voices: ["en_US-amy-medium"],
    license: "MIT",
  },
];

const AVAILABLE: AvailableModel[] = [
  {
    name: "kokoro-v1.0",
    type: "engine",
    size_mb: 300,
    license: "Apache-2.0",
    requires_gpu: true,
    install_hint: "pip install hypnoai[kokoro]",
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ModelManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRpc.modelsStatus.mockResolvedValue(STATUS);
    mockRpc.modelsList.mockResolvedValue({
      installed: [],
      available_for_download: [],
    });
    mockRpc.modelsDownload.mockResolvedValue({ job_id: "j1", size_mb: 300 });
    mockRpc.modelsRemove.mockResolvedValue({ freed_mb: 26 });
    mockRpc.modelsDownloadProgress.mockResolvedValue({
      state: "downloading",
      progress_pct: 50,
      speed_mbps: 10,
      error: null,
    });
  });

  // --- Loading / error states ---

  it("shows loading spinner initially", () => {
    // Never resolves — keeps the component in loading state
    mockRpc.modelsStatus.mockImplementation(() => new Promise(() => {}));
    render(<ModelManager />);
    expect(screen.getByText(/Loading model information/)).toBeInTheDocument();
  });

  it("shows error message when the RPC call fails", async () => {
    mockRpc.modelsStatus.mockRejectedValue(new Error("connection refused"));
    render(<ModelManager />);
    await waitFor(() =>
      expect(
        screen.getByText(/Model information unavailable/)
      ).toBeInTheDocument()
    );
  });

  it("shows 'No models installed' when both lists are empty", async () => {
    render(<ModelManager />);
    await waitFor(() =>
      expect(
        screen.getByText(/No models installed yet/)
      ).toBeInTheDocument()
    );
  });

  // --- Installed models ---

  it("shows installed model name and engine", async () => {
    mockRpc.modelsList.mockResolvedValue({
      installed: INSTALLED,
      available_for_download: [],
    });
    render(<ModelManager />);
    await waitFor(() =>
      expect(screen.getByText("en_US-amy-medium")).toBeInTheDocument()
    );
    expect(screen.getByText(/piper/)).toBeInTheDocument();
  });

  it("calls modelsRemove after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockRpc.modelsList.mockResolvedValue({
      installed: INSTALLED,
      available_for_download: [],
    });
    render(<ModelManager />);
    await waitFor(() => screen.getByText("en_US-amy-medium"));
    await user.click(screen.getByRole("button", { name: /remove/i }));
    expect(mockRpc.modelsRemove).toHaveBeenCalledWith("en_US-amy-medium");
  });

  it("does not call modelsRemove when confirmation is cancelled", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mockRpc.modelsList.mockResolvedValue({
      installed: INSTALLED,
      available_for_download: [],
    });
    render(<ModelManager />);
    await waitFor(() => screen.getByText("en_US-amy-medium"));
    await user.click(screen.getByRole("button", { name: /remove/i }));
    expect(mockRpc.modelsRemove).not.toHaveBeenCalled();
  });

  // --- Available models ---

  it("shows available model name and license", async () => {
    mockRpc.modelsList.mockResolvedValue({
      installed: [],
      available_for_download: AVAILABLE,
    });
    render(<ModelManager />);
    await waitFor(() =>
      expect(screen.getByText("kokoro-v1.0")).toBeInTheDocument()
    );
    expect(screen.getByText(/Apache-2\.0/)).toBeInTheDocument();
  });

  it("shows GPU badge for GPU-required models", async () => {
    mockRpc.modelsList.mockResolvedValue({
      installed: [],
      available_for_download: AVAILABLE,
    });
    render(<ModelManager />);
    await waitFor(() =>
      expect(screen.getByText("GPU")).toBeInTheDocument()
    );
  });

  it("shows install hint for available models", async () => {
    mockRpc.modelsList.mockResolvedValue({
      installed: [],
      available_for_download: AVAILABLE,
    });
    render(<ModelManager />);
    await waitFor(() =>
      expect(
        screen.getByText(/pip install hypnoai\[kokoro\]/)
      ).toBeInTheDocument()
    );
  });

  it("calls modelsDownload with the model name when Download is clicked", async () => {
    const user = userEvent.setup();
    mockRpc.modelsList.mockResolvedValue({
      installed: [],
      available_for_download: AVAILABLE,
    });
    render(<ModelManager />);
    await waitFor(() => screen.getByText("kokoro-v1.0"));
    await user.click(screen.getByRole("button", { name: /download/i }));
    expect(mockRpc.modelsDownload).toHaveBeenCalledWith("kokoro-v1.0");
  });

  // --- Status bar ---

  it('shows "CPU only" when GPU is not available', async () => {
    render(<ModelManager />);
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
    render(<ModelManager />);
    await waitFor(() =>
      expect(screen.getByText(/GPU available/)).toBeInTheDocument()
    );
  });

  // --- First-launch mode ---

  it("shows first-launch header when isFirstLaunch=true", async () => {
    render(<ModelManager isFirstLaunch={true} />);
    await waitFor(() =>
      expect(screen.getByText(/Welcome to HypnoAI/)).toBeInTheDocument()
    );
  });

  it("'Get Started' button is disabled when nothing is installed", async () => {
    render(<ModelManager isFirstLaunch={true} onClose={vi.fn()} />);
    await waitFor(() => screen.getByText(/No models installed/));
    expect(
      screen.getByRole("button", { name: /Get Started/ })
    ).toBeDisabled();
  });

  it("'Get Started' button is enabled after a model is installed", async () => {
    mockRpc.modelsList.mockResolvedValue({
      installed: INSTALLED,
      available_for_download: [],
    });
    render(<ModelManager isFirstLaunch={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Get Started/ })
      ).not.toBeDisabled()
    );
  });
});
