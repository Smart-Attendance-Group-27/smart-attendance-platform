"use client";

import { Button } from "@/components/ui/Button";
import { downloadCsv, toCsv } from "@/lib/csv";

type ExportCsvButtonProps = {
  filenamePrefix: string;
  headers: string[];
  rows: (string | number)[][];
  label?: string;
};

// Exports rows the page already shows, so nothing is fetched or invented.
export function ExportCsvButton({ filenamePrefix, headers, rows, label = "Export CSV" }: ExportCsvButtonProps) {
  function exportRows() {
    const date = new Date().toISOString().slice(0, 10);
    downloadCsv(`${filenamePrefix}-${date}.csv`, toCsv(headers, rows));
  }

  return (
    <Button onClick={exportRows} disabled={rows.length === 0} title={rows.length === 0 ? "There is nothing to export yet." : undefined}>
      {label}
    </Button>
  );
}
