import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { embeddingGenerationStatusDisplay, readinessStatusDisplay } from "@/lib/status";
import { ReferenceFaceRecord } from "@/types/admin";

export function ReferenceFaceTable({ records }: { records: ReferenceFaceRecord[] }) {
  return (
    <Card title="Reference-face governance" className="border-l-4 border-l-[var(--uom-gold)]" flush>
      <DataTable<ReferenceFaceRecord>
        emptyTitle="No reference-face records"
        emptyDescription="Student face enrolment status will appear here."
        columns={[
          {
            key: "student",
            header: "Student",
            render: (row) => <CellPrimary primary={row.studentName} secondary={row.registrationNumber} />,
          },
          {
            key: "generation",
            header: "Enrolment status",
            render: (row) => {
              const display = embeddingGenerationStatusDisplay(row.embeddingGenerationStatus);
              return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
            },
          },
          {
            key: "readiness",
            header: "Readiness",
            render: (row) => {
              const display = readinessStatusDisplay(row.readinessStatus);
              return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
            },
          },
          { key: "generated", header: "Last generated", render: (row) => row.generatedAtLabel ?? "—" },
          { key: "checked", header: "Readiness checked", render: (row) => row.readinessCheckedAtLabel ?? "—" },
          {
            key: "action",
            header: "Action",
            align: "right",
            render: () => (
              <Button title="Available once reference-face governance API is integrated" disabled>
                Revoke
              </Button>
            ),
          },
        ]}
        rows={records}
        getRowKey={(row) => row.studentId}
      />
    </Card>
  );
}
