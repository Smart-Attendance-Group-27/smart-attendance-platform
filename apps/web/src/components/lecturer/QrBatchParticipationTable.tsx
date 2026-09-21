import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDateTimeLabel } from "@/lib/api/format";
import type { LecturerQrBatch } from "@/types/lecturer";

export function QrBatchParticipationTable({ batches }: { batches: LecturerQrBatch[] }) {
  const newestFirst = [...batches].sort((a, b) => b.activatedAt.localeCompare(a.activatedAt));
  return (
    <Card title="QR batch participation" subtitle="Newest batch first" flush>
      <DataTable<LecturerQrBatch>
        emptyTitle="No QR batches yet"
        emptyDescription="Launch a QR batch to see participation here."
        columns={[
          { key: "batch", header: "Batch", render: (row) => <span className="font-mono text-[11px]">{row.qrSessionId}</span> },
          { key: "mode", header: "Mode", render: (row) => <span className="capitalize">{row.mode}</span> },
          { key: "status", header: "Status", render: (row) => (
            <span>
              <StatusBadge tone={row.voided ? "danger" : row.status === "active" ? "success" : "neutral"}>
                {row.voided ? "Voided" : row.status}
              </StatusBadge>
              {row.voidReason ? <span className="mt-1 block text-[10px] text-[var(--muted)]">{row.voidReason}</span> : null}
            </span>
          ) },
          { key: "activated", header: "Activated", render: (row) => formatDateTimeLabel(row.activatedAt) },
          { key: "deactivated", header: "Deactivated", render: (row) => formatDateTimeLabel(row.deactivatedAt) },
          { key: "expires", header: "Expires", render: (row) => formatDateTimeLabel(row.expiresAt) },
          { key: "participation", header: "Passed / required", render: (row) =>
            `${row.passedStudentCount}/${row.requiredStudentCount}` },
        ]}
        rows={newestFirst}
        getRowKey={(row) => row.qrSessionId}
      />
    </Card>
  );
}
