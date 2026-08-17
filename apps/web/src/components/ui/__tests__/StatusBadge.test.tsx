import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/ui/StatusBadge";

describe("StatusBadge", () => {
  it("renders its label text", () => {
    render(<StatusBadge tone="success">Present</StatusBadge>);
    expect(screen.getByText("Present")).toBeInTheDocument();
  });

  it("defaults to the neutral tone when none is given", () => {
    render(<StatusBadge>Unknown</StatusBadge>);
    expect(screen.getByText("Unknown").className).toContain("text-[#52606b]");
  });
});
