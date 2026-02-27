import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PacingHeatmap } from "../components/PacingHeatmap";
import type { PacingEntry } from "../types";

const PACING: PacingEntry[] = [
  { paragraph: 0, wpm: 50 },  // slow  → blue
  { paragraph: 1, wpm: 70 },  // ideal → green
  { paragraph: 2, wpm: 90 },  // fast  → yellow
  { paragraph: 3, wpm: 110 }, // too fast → red
];

describe("PacingHeatmap", () => {
  it("renders nothing when visible=false", () => {
    const { container } = render(
      <PacingHeatmap pacing={PACING} paragraphCount={4} visible={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when pacing array is empty", () => {
    const { container } = render(
      <PacingHeatmap pacing={[]} paragraphCount={0} visible={true} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows WPM value for each entry", () => {
    render(<PacingHeatmap pacing={PACING} paragraphCount={4} visible={true} />);
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("70")).toBeInTheDocument();
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.getByText("110")).toBeInTheDocument();
  });

  it("shows 1-based paragraph numbers", () => {
    render(<PacingHeatmap pacing={PACING} paragraphCount={4} visible={true} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("encodes correct WPM labels in title attributes", () => {
    render(<PacingHeatmap pacing={PACING} paragraphCount={4} visible={true} />);
    expect(document.querySelector('[title*="slow"]')).toBeInTheDocument();
    expect(document.querySelector('[title*="ideal"]')).toBeInTheDocument();
    expect(document.querySelector('[title*="too fast"]')).toBeInTheDocument();
  });

  it("shows notice when fewer pacing entries than paragraphs", () => {
    render(
      <PacingHeatmap pacing={[PACING[0]]} paragraphCount={4} visible={true} />
    );
    expect(
      screen.getByText(/Render to see full heatmap/)
    ).toBeInTheDocument();
  });

  it("does not show partial notice when all paragraphs are covered", () => {
    render(<PacingHeatmap pacing={PACING} paragraphCount={4} visible={true} />);
    expect(
      screen.queryByText(/Render to see full heatmap/)
    ).not.toBeInTheDocument();
  });

  it("renders the legend with all four speed bands", () => {
    render(<PacingHeatmap pacing={PACING} paragraphCount={4} visible={true} />);
    // The legend section renders these label texts
    expect(screen.getByText(/slow ≤60/)).toBeInTheDocument();
    expect(screen.getByText(/ideal 60–80/)).toBeInTheDocument();
    expect(screen.getByText(/fast 80–100/)).toBeInTheDocument();
    expect(screen.getByText(/too fast >100/)).toBeInTheDocument();
  });

  it("applies blue colour class for WPM ≤ 60", () => {
    render(
      <PacingHeatmap
        pacing={[{ paragraph: 0, wpm: 45 }]}
        paragraphCount={1}
        visible={true}
      />
    );
    expect(document.querySelector(".bg-blue-400\\/60")).toBeInTheDocument();
  });

  it("applies green colour class for WPM in 61–80 range", () => {
    render(
      <PacingHeatmap
        pacing={[{ paragraph: 0, wpm: 75 }]}
        paragraphCount={1}
        visible={true}
      />
    );
    expect(document.querySelector(".bg-green-400\\/60")).toBeInTheDocument();
  });

  it("applies red colour class for WPM > 100", () => {
    render(
      <PacingHeatmap
        pacing={[{ paragraph: 0, wpm: 120 }]}
        paragraphCount={1}
        visible={true}
      />
    );
    expect(document.querySelector(".bg-red-400\\/60")).toBeInTheDocument();
  });
});
