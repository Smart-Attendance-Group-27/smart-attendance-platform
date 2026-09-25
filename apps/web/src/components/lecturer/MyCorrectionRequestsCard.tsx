import { Card } from "@/components/ui/Card";
import { CellPrimary, DataTable } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { CorrectionRequestRow } from "@/lib/correctionRequests";
import { correctionStatusDisplay } from "@/lib/status";

export function MyCorrectionRequestsCard({ requests }: { requests: CorrectionRequestRow[] }) {
  return (
    <Card title="My correction requests" subtitle="Submitted for administrative review" flush>
      <DataTable<CorrectionRequestRow>
        emptyTitle="No correction requests yet"
        emptyDescription="Requests you submit from this page appear here with their review status."
        columns={[
          { key: "created", header: "Submitted", render: (row) => row.createdLabel },
          {
            key: "request",
            header: "Request",
            render: (row) => (
              <CellPrimary
                primary={`${row.typeLabel} · ${row.categoryLabel}`}
                secondary={row.targetLabel === "—" ? row.courseLabel : `${row.courseLabel} · ${row.targetLabel}`}
              />
            ),
          },
          {
            key: "status",
            header: "Status",
            render: (row) => {
              const display = correctionStatusDisplay(row.status);
              return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
            },
          },
          {
            key: "note",
            header: "Administrator's note",
            render: (row) => <span className="whitespace-normal">{row.reviewNote ?? "—"}</span>,
          },
        ]}
        rows={requests}
        getRowKey={(row) => row.id}
      />
    </Card>
  );
}
