import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable } from "@/components/ui/DataTable";

type Row = { id: string; name: string };

const ROWS: Row[] = [
  { id: "1", name: "CS3203" },
  { id: "2", name: "CS2101" },
];

const COLUMNS = [{ key: "name", header: "Course", render: (row: Row) => row.name }];

describe("DataTable", () => {
  it("renders one row per item with the given columns", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(row) => row.id} />);
    expect(screen.getByText("CS3203")).toBeInTheDocument();
    expect(screen.getByText("CS2101")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3); // header + 2 rows
  });

  it("shows an empty state instead of an empty table when there are no rows", () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        getRowKey={(row) => row.id}
        emptyTitle="No courses yet"
        emptyDescription="Assigned courses will appear here."
      />,
    );
    expect(screen.getByText("No courses yet")).toBeInTheDocument();
    expect(screen.getByText("Assigned courses will appear here.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("calls onRowClick with the clicked row", async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(row) => row.id} onRowClick={onRowClick} />);

    await user.click(screen.getByText("CS2101"));

    expect(onRowClick).toHaveBeenCalledWith(ROWS[1]);
  });
});
