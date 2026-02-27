import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { useState } from "react";
import { VariablesPanel } from "../components/VariablesPanel";
import type { LintResult } from "../types";

const LINT: LintResult = {
  valid: true,
  warnings: [],
  paragraph_count: 2,
  pause_count: 1,
  section_count: 1,
  estimated_duration_s: 60,
  variables: ["name", "safe_place"],
  pacing: [],
};

describe("VariablesPanel", () => {
  it("shows empty message when lint result has no variables", () => {
    render(
      <VariablesPanel
        variables={{}}
        onChange={vi.fn()}
        lintResult={{ ...LINT, variables: [] }}
      />
    );
    expect(screen.getByText(/No variables detected/)).toBeInTheDocument();
  });

  it("shows empty message when lintResult is null", () => {
    render(
      <VariablesPanel variables={{}} onChange={vi.fn()} lintResult={null} />
    );
    expect(screen.getByText(/No variables detected/)).toBeInTheDocument();
  });

  it("renders an input for each variable in the lint result", () => {
    render(
      <VariablesPanel variables={{}} onChange={vi.fn()} lintResult={LINT} />
    );
    expect(
      screen.getByPlaceholderText("Enter name…")
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter safe_place…")
    ).toBeInTheDocument();
  });

  it("renders variable labels with {{}} syntax", () => {
    render(
      <VariablesPanel variables={{}} onChange={vi.fn()} lintResult={LINT} />
    );
    expect(screen.getByText("{{name}}")).toBeInTheDocument();
    expect(screen.getByText("{{safe_place}}")).toBeInTheDocument();
  });

  it("populates input with existing variable value", () => {
    render(
      <VariablesPanel
        variables={{ name: "Alice" }}
        onChange={vi.fn()}
        lintResult={LINT}
      />
    );
    expect(screen.getByDisplayValue("Alice")).toBeInTheDocument();
  });

  it("calls onChange with updated map when user types", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    // Use a stateful wrapper so the controlled input accumulates keystrokes
    function Wrapper() {
      const [vars, setVars] = useState<Record<string, string>>({});
      return (
        <VariablesPanel
          variables={vars}
          onChange={(newVars) => { setVars(newVars); onChange(newVars); }}
          lintResult={LINT}
        />
      );
    }
    render(<Wrapper />);
    await user.type(screen.getByPlaceholderText("Enter name…"), "Bob");
    expect(onChange).toHaveBeenCalled();
    // Each keystroke calls onChange; the last call should have name='Bob'
    const lastArg = onChange.mock.calls.at(-1)?.[0] as Record<string, string>;
    expect(lastArg.name).toBe("Bob");
  });

  it("shows variables from the values map even if absent from lint result", () => {
    render(
      <VariablesPanel
        variables={{ custom_var: "hello" }}
        onChange={vi.fn()}
        lintResult={{ ...LINT, variables: [] }}
      />
    );
    expect(
      screen.getByPlaceholderText("Enter custom_var…")
    ).toBeInTheDocument();
  });

  it("deduplicates variables that appear in both lint result and values map", () => {
    render(
      <VariablesPanel
        variables={{ name: "Alice" }}
        onChange={vi.fn()}
        lintResult={LINT}
      />
    );
    // Should render exactly one input for 'name'
    const inputs = screen.getAllByPlaceholderText("Enter name…");
    expect(inputs).toHaveLength(1);
  });
});
