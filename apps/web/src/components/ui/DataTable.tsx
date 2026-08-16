import { ReactNode } from "react";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
};

export function DataTable<T>({ columns, rows, getRowKey, onRowClick }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-xs">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={`whitespace-nowrap border-b border-[var(--line)] bg-[#f5f7f9] px-2.5 py-2.5 font-semibold text-[#53616d] ${
                  column.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getRowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`border-b border-[var(--line-soft)] last:border-b-0 ${
                onRowClick ? "cursor-pointer hover:bg-[#f7fbfe]" : ""
              }`}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-2.5 py-2.5 align-middle ${column.align === "right" ? "text-right" : ""}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CellPrimary({ primary, secondary }: { primary: ReactNode; secondary?: ReactNode }) {
  return (
    <span>
      <span className="font-semibold text-[var(--link)]">{primary}</span>
      {secondary ? <span className="mt-0.5 block text-[10px] font-normal text-[var(--muted)]">{secondary}</span> : null}
    </span>
  );
}
