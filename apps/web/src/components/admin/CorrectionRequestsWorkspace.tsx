"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { decideCorrectionRequest } from "@/app/actions/corrections";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { Dialog } from "@/components/ui/Dialog";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { allowedDecisions, type CorrectionDecision, type CorrectionRequestRow } from "@/lib/correctionRequests";
import { correctionStatusDisplay } from "@/lib/status";

const DECISION_LABELS: Record<CorrectionDecision, string> = {
  approved: "Approve",
  rejected: "Reject",
  resolved: "Mark as resolved",
};

export function CorrectionRequestsWorkspace({ requests }: { requests: CorrectionRequestRow[] }) {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [reviewing, setReviewing] = useState<CorrectionRequestRow | null>(null);
  const [decision, setDecision] = useState<CorrectionDecision | "">("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visible = useMemo(
    () => (statusFilter === "all" ? requests : requests.filter((request) => request.status === statusFilter)),
    [requests, statusFilter],
  );
  const pendingCount = requests.filter((request) => request.status === "pending").length;

  function openReview(request: CorrectionRequestRow) {
    setReviewing(request);
    setDecision(allowedDecisions(request.status)[0] ?? "");
    setNote("");
    setError(null);
  }

  function close() {
    if (busy) return;
    setReviewing(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !reviewing) return;
    if (!decision) {
      setError("Choose a decision.");
      return;
    }
    if (decision === "rejected" && note.trim().length < 3) {
      setError("Give the lecturer a reason for rejecting the request.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const result = await decideCorrectionRequest(reviewing.id, reviewing.status, decision, note);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setReviewing(null);
      router.refresh();
    } catch {
      setError("Couldn't save the decision. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Card
        title="Correction requests"
        subtitle={`${pendingCount} pending`}
        flush
      >
        <FilterBar>
          <FilterSelect
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="resolved">Resolved</option>
            <option value="all">All requests</option>
          </FilterSelect>
        </FilterBar>
        <DataTable<CorrectionRequestRow>
          emptyTitle="No correction requests"
          emptyDescription="Requests lecturers submit for academic data or timetable changes appear here."
          columns={[
            { key: "created", header: "Submitted", render: (row) => row.createdLabel },
            { key: "requester", header: "Lecturer", render: (row) => row.requesterName },
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
            { key: "details", header: "Details", render: (row) => <span className="whitespace-normal">{row.description}</span> },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = correctionStatusDisplay(row.status);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
            {
              key: "action",
              header: "Action",
              align: "right",
              render: (row) =>
                allowedDecisions(row.status).length > 0 ? (
                  <Button onClick={() => openReview(row)}>Review</Button>
                ) : (
                  <span className="text-[11px] text-[var(--muted)]">{row.reviewedLabel ?? "—"}</span>
                ),
            },
          ]}
          rows={visible}
          getRowKey={(row) => row.id}
        />
      </Card>

      {reviewing ? (
        <Dialog open title="Review correction request" onClose={close}>
          <form onSubmit={(event) => { void submit(event); }} className="space-y-4">
            <div className="space-y-1 text-xs">
              <p>
                <strong>{reviewing.requesterName}</strong> · {reviewing.typeLabel} · {reviewing.categoryLabel}
              </p>
              <p className="text-[var(--muted)]">
                {reviewing.courseLabel}
                {reviewing.targetLabel === "—" ? "" : ` · ${reviewing.targetLabel}`}
              </p>
              <p className="whitespace-pre-wrap">{reviewing.description}</p>
            </div>
            <p className="text-xs text-[var(--muted)]">
              Deciding a request does not change any academic record. Make the change in Academic data, then mark the
              request resolved.
            </p>
            <FormField htmlFor="correction-decision" label="Decision">
              <select
                id="correction-decision"
                className={fieldInputClassName()}
                value={decision}
                disabled={busy}
                onChange={(event) => setDecision(event.target.value as CorrectionDecision)}
              >
                {allowedDecisions(reviewing.status).map((option) => (
                  <option key={option} value={option}>
                    {DECISION_LABELS[option]}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField
              htmlFor="correction-note"
              label="Note to the lecturer"
              help={decision === "rejected" ? "Required when rejecting." : "Optional."}
            >
              <textarea
                id="correction-note"
                className={`${fieldInputClassName()} min-h-24 resize-y py-2`}
                maxLength={1000}
                value={note}
                disabled={busy}
                onChange={(event) => setNote(event.target.value)}
              />
            </FormField>
            {error ? <p role="alert" className="text-xs text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-2">
              <Button onClick={close} disabled={busy}>Cancel</Button>
              <Button type="submit" variant="primary" disabled={busy}>
                {busy ? "Saving..." : "Save decision"}
              </Button>
            </div>
          </form>
        </Dialog>
      ) : null}
    </>
  );
}
