import type { ApiFinalizationSummary } from "@/lib/api/lecturer";

export function FinalizationSummary({ summary }: { summary: ApiFinalizationSummary | null }) {
  if (summary === null) {
    return (
      <p className="text-xs leading-relaxed text-[var(--muted)]">
        The session is closed. Final attendance counts are not available yet.
      </p>
    );
  }

  const counts = [
    { label: "Enrolled", value: summary.enrolledCount },
    { label: "Present", value: summary.presentCount },
    { label: "Late", value: summary.lateCount },
    { label: "Absent", value: summary.absentCount },
    { label: "Manual records kept", value: summary.keptManualCount },
    { label: "Check-ins reconciled", value: summary.reconciledCount },
    { label: "QR batches deactivated", value: summary.deactivatedQrBatchCount },
  ];

  return (
    <div>
      <p className="mb-3 text-xs text-[var(--muted)]">Final attendance at session close</p>
      <dl className="grid grid-cols-2 gap-2">
        {counts.map(({ label, value }) => (
          <div key={label} className="border border-[var(--line)] p-2">
            <dt className="text-[10px] text-[var(--muted)]">{label}</dt>
            <dd className="mt-1 text-sm font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-[10px] text-[var(--muted)]">
        Finalized {new Date(summary.finalizedAt).toLocaleString()}
      </p>
    </div>
  );
}
