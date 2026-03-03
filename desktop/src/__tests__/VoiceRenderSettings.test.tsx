import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { VoiceRenderSettings } from "../components/VoiceRenderSettings";
import type { RenderProgress, RenderSettings, VoiceInfo } from "../types";

const SETTINGS: RenderSettings = {
  engine: "piper",
  voice: "en_US-amy-medium",
  speed: 0.85,
  pitch: 0,
  emotion: "",
};

const VOICES: VoiceInfo[] = [
  {
    id: "en_US-amy-medium",
    name: "Amy",
    language: "en-us",
    quality: "medium",
    sample_rate: 22050,
    size_mb: 26,
    is_custom: false,
    engine: "piper",
  },
  {
    id: "af",
    name: "Af",
    language: "en-us",
    quality: "high",
    sample_rate: 24000,
    size_mb: 0,
    is_custom: false,
    engine: "kokoro",
  },
];

function makeProps(overrides: Record<string, unknown> = {}) {
  return {
    settings: SETTINGS,
    onSettingsChange: vi.fn(),
    voices: VOICES,
    engines: ["piper", "kokoro"],
    renderProgress: null,
    isRendering: false,
    onRender: vi.fn(),
    onCancelRender: vi.fn(),
    outputPath: "session.wav",
    onOutputPathChange: vi.fn(),
    onClearCache: vi.fn(),
    onOpenInFolder: vi.fn(),
    ...overrides,
  };
}

describe("VoiceRenderSettings", () => {
  // --- Engine & voice selects ---

  it("shows all engine options", () => {
    render(<VoiceRenderSettings {...makeProps()} />);
    expect(screen.getByDisplayValue("piper")).toBeInTheDocument();
  });

  it("filters the voice list to the selected engine", () => {
    render(<VoiceRenderSettings {...makeProps()} />);
    // Amy belongs to piper — should be present
    expect(screen.getByText(/Amy \(en-us/)).toBeInTheDocument();
    // Af belongs to kokoro — should be absent
    expect(screen.queryByText(/^Af \(/)).not.toBeInTheDocument();
  });

  it("calls onSettingsChange with empty voice when engine changes", async () => {
    const user = userEvent.setup();
    const onSettingsChange = vi.fn();
    render(<VoiceRenderSettings {...makeProps({ onSettingsChange })} />);
    const engineSelect = screen.getByDisplayValue("piper");
    await user.selectOptions(engineSelect, "kokoro");
    expect(onSettingsChange).toHaveBeenCalledWith(
      expect.objectContaining({ engine: "kokoro", voice: "" })
    );
  });

  // --- Render button ---

  it("render button is enabled when voice and outputPath are set", () => {
    render(<VoiceRenderSettings {...makeProps()} />);
    expect(screen.getByRole("button", { name: /render$/i })).not.toBeDisabled();
  });

  it("render button is disabled when no voice is selected", () => {
    render(
      <VoiceRenderSettings
        {...makeProps({ settings: { ...SETTINGS, voice: "" } })}
      />
    );
    expect(screen.getByRole("button", { name: /render$/i })).toBeDisabled();
  });

  it("render button is disabled when outputPath is empty", () => {
    render(<VoiceRenderSettings {...makeProps({ outputPath: "" })} />);
    expect(screen.getByRole("button", { name: /render$/i })).toBeDisabled();
  });

  it("calls onRender when render button is clicked", async () => {
    const user = userEvent.setup();
    const onRender = vi.fn();
    render(<VoiceRenderSettings {...makeProps({ onRender })} />);
    await user.click(screen.getByRole("button", { name: /render$/i }));
    expect(onRender).toHaveBeenCalledOnce();
  });

  // --- Cancel button (shown while rendering) ---

  it("shows cancel button instead of render when isRendering=true", () => {
    render(<VoiceRenderSettings {...makeProps({ isRendering: true })} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^.*render$/i })
    ).not.toBeInTheDocument();
  });

  it("calls onCancelRender when cancel is clicked", async () => {
    const user = userEvent.setup();
    const onCancelRender = vi.fn();
    render(
      <VoiceRenderSettings
        {...makeProps({ isRendering: true, onCancelRender })}
      />
    );
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancelRender).toHaveBeenCalledOnce();
  });

  // --- Progress bar ---

  it("shows paragraph progress while rendering", () => {
    const progress: RenderProgress = {
      state: "rendering",
      current_paragraph: 3,
      total: 10,
      chunk_paths: [],
      elapsed_s: 8,
      error: null,
    };
    render(<VoiceRenderSettings {...makeProps({ renderProgress: progress })} />);
    expect(screen.getByText(/Paragraph 3\/10/)).toBeInTheDocument();
  });

  it('shows "Done" text when render is complete', () => {
    const progress: RenderProgress = {
      state: "done",
      current_paragraph: 10,
      total: 10,
      chunk_paths: [],
      elapsed_s: 30,
      error: null,
    };
    render(<VoiceRenderSettings {...makeProps({ renderProgress: progress })} />);
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("shows error message when render fails", () => {
    const progress: RenderProgress = {
      state: "failed",
      current_paragraph: 2,
      total: 10,
      chunk_paths: [],
      elapsed_s: 4,
      error: "out of memory",
    };
    render(<VoiceRenderSettings {...makeProps({ renderProgress: progress })} />);
    expect(screen.getByText(/out of memory/)).toBeInTheDocument();
  });

  it("does not show progress bar when renderProgress is null", () => {
    render(<VoiceRenderSettings {...makeProps({ renderProgress: null })} />);
    expect(screen.queryByText(/Paragraph/)).not.toBeInTheDocument();
  });
});
