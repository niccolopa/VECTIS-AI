import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/Button";
import { RiskBadge } from "@/components/ui/risk";

describe("Button", () => {
  it("renders its label and fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Run analysis</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and non-interactive while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("RiskBadge", () => {
  it("renders the human-readable band label", () => {
    render(<RiskBadge band="severe" />);
    expect(screen.getByText("Severe")).toBeInTheDocument();
  });
});
