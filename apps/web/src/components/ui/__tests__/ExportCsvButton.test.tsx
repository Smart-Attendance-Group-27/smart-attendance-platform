import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExportCsvButton } from "@/components/ui/ExportCsvButton";
import { downloadCsv } from "@/lib/csv";

vi.mock("@/lib/csv", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/csv")>()),
  downloadCsv: vi.fn(),
}));

beforeEach(() => vi.clearAllMocks());

describe("ExportCsvButton", () => {
  it("downloads the rows it was given, with headings, under a dated filename", async () => {
    const user = userEvent.setup();
    render(<ExportCsvButton filenamePrefix="report" headers={["A", "B"]} rows={[["x,y", 2]]} />);

    await user.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(downloadCsv).toHaveBeenCalledWith(expect.stringMatching(/^report-\d{4}-\d{2}-\d{2}\.csv$/), 'A,B\r\n"x,y",2');
  });

  it("is disabled when there is nothing to export", () => {
    render(<ExportCsvButton filenamePrefix="report" headers={["A"]} rows={[]} />);

    expect(screen.getByRole("button", { name: "Export CSV" })).toBeDisabled();
  });
});
