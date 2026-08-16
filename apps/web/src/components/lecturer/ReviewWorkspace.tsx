"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { FilterBar, SearchInput, FilterSelect } from "@/components/ui/FilterBar";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Dialog } from "@/components/ui/Dialog";
import { ConfirmationDialog } from "@/components/ui/Dialog";
import { Notice } from "@/components/ui/Notice";
import { geofenceResultDisplay, reviewCaseStatusDisplay } from "@/lib/status";
import { ReviewCase } from "@/types/lecturer";
import { ReviewDecisionKind, submitReviewDecision } from "@/app/actions/review";

type DecisionKind = ReviewDecisionKind;

function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function ReviewWorkspace({ initialCases }: { initialCases: ReviewCase[] }) {
  const [cases, setCases] = useState(initialCases);
  const [selectedId, setSelectedId] = useState<string | null>(initialCases[0]?.caseId ?? null);
  const [query, setQuery] = useState("");
  const [pendingDecision, setPendingDecision] = useState<DecisionKind | null>(null);
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return cases;
    return cases.filter(
      (item) =>
        item.studentName.toLowerCase().includes(normalized) || item.studentIndex.toLowerCase().includes(normalized),
    );
  }, [cases, query]);

  const selected = cases.find((item) => item.caseId === selectedId) ?? null;

  async function resolveSelected(kind: DecisionKind) {
    if (!selected) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await submitReviewDecision(selected.caseId, kind, reason.trim() || undefined);
      const remaining = cases.filter((item) => item.caseId !== selected.caseId);
      setCases(remaining);
      setSelectedId(remaining[0]?.caseId ?? null);
      setPendingDecision(null);
      setReason("");
    } catch {
      setSubmitError("Couldn't submit this decision. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card flush>
      <FilterBar>
        <FilterSelect>
          <option>All assigned courses</option>
        </FilterSelect>
        <FilterSelect>
          <option>All issue types</option>
        </FilterSelect>
        <FilterSelect>
          <option>Pending</option>
        </FilterSelect>
        <SearchInput
          placeholder="Student name or index number"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </FilterBar>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_345px]">
        <div className="overflow-x-auto">
            <DataTable<ReviewCase>
              emptyTitle={cases.length === 0 ? "No cases pending review" : "No matching cases"}
              emptyDescription={cases.length === 0 ? "New verification issues will appear here." : "Adjust your search or filters."}
              columns={[
                {
                  key: "student",
                  header: "Student",
                  render: (row) => <CellPrimary primary={row.studentName} secondary={row.studentIndex} />,
                },
                { key: "course", header: "Course", render: (row) => row.courseCode },
                { key: "issue", header: "Issue", render: (row) => row.issueLabel },
                {
                  key: "face",
                  header: "Face score",
                  render: (row) => (
                    <StatusBadge tone={row.faceScorePercent < 70 ? "danger" : "success"}>
                      {row.faceScorePercent}%
                    </StatusBadge>
                  ),
                },
                {
                  key: "geofence",
                  header: "Geofence",
                  render: (row) => {
                    const display = geofenceResultDisplay(row.geofenceResult);
                    return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
                  },
                },
                { key: "time", header: "Time", render: (row) => row.time },
                {
                  key: "status",
                  header: "Status",
                  render: (row) => {
                    const display = reviewCaseStatusDisplay(row.status);
                    return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
                  },
                },
              ]}
              rows={filtered}
              getRowKey={(row) => row.caseId}
              onRowClick={(row) => setSelectedId(row.caseId)}
            />
        </div>

        <aside aria-label="Selected verification case" className="border-t border-[var(--line)] bg-[#fbfcfd] p-4 lg:border-l lg:border-t-0">
          {!selected ? (
            <EmptyState title="No case selected" description="Choose a row from the table to review its evidence." />
          ) : (
            <>
              <div className="flex items-center gap-2.5 border-b border-[var(--line)] pb-3">
                <span className="grid h-11 w-11 place-items-center rounded-full bg-[#dde8f0] font-bold text-[var(--uom-blue)]">
                  {initialsFor(selected.studentName)}
                </span>
                <div>
                  <strong className="block text-sm">{selected.studentName}</strong>
                  <small className="mt-0.5 block text-[11px] text-[var(--muted)]">
                    {selected.studentIndex} · {selected.studentProgramme}
                  </small>
                </div>
              </div>

              <div className="mt-4 border border-[var(--line)] bg-white">
                <div className="border-b border-[var(--line)] bg-[#f5f7f9] px-2.5 py-2 text-[11px] font-semibold">
                  Submitted face image · {selected.time}
                </div>
                <div className="grid h-[145px] place-items-center bg-gradient-to-br from-[#d8dde1] to-[#b8c0c7] text-xs text-[#5a6570]">
                  Face capture preview withheld in prototype
                </div>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="border border-[var(--line)] bg-white p-2.5">
                  <small className="block text-[9px] uppercase text-[var(--muted)]">Face match</small>
                  <strong className={`mt-1 block text-[11px] ${selected.faceScorePercent < 70 ? "text-[var(--danger)]" : "text-[var(--success)]"}`}>
                    {selected.faceScorePercent}% {selected.faceScorePercent < 70 ? "· Below threshold" : ""}
                  </strong>
                </div>
                <div className="border border-[var(--line)] bg-white p-2.5">
                  <small className="block text-[9px] uppercase text-[var(--muted)]">Liveness</small>
                  <strong className="mt-1 block text-[11px] text-[var(--success)]">
                    {selected.livenessPassed ? "Passed" : "Failed"}
                  </strong>
                </div>
                <div className="border border-[var(--line)] bg-white p-2.5">
                  <small className="block text-[9px] uppercase text-[var(--muted)]">Geofence</small>
                  <strong className="mt-1 block text-[11px] text-[var(--success)]">
                    Within {selected.geofenceDistanceMeters} m
                  </strong>
                </div>
                <div className="border border-[var(--line)] bg-white p-2.5">
                  <small className="block text-[9px] uppercase text-[var(--muted)]">QR event</small>
                  <strong className="mt-1 block text-[11px]">{selected.qrEventLabel}</strong>
                </div>
              </div>

              <Notice variant="warning" title="Review reason:">
                {selected.reviewReason}
              </Notice>

              <div className="mt-3.5 grid grid-cols-2 gap-1.5">
                <Button variant="primary" onClick={() => setPendingDecision("approve")}>
                  Approve attendance
                </Button>
                <Button variant="danger" onClick={() => setPendingDecision("reject")}>
                  Reject
                </Button>
                <Button onClick={() => setPendingDecision("retry")}>Request retry</Button>
                <Button onClick={() => setPendingDecision("escalate")}>Escalate</Button>
              </div>
            </>
          )}
        </aside>
      </div>

      {(pendingDecision === "approve" || pendingDecision === "reject") && selected ? (
        <Dialog
          open
          title={pendingDecision === "approve" ? "Approve attendance" : "Reject attendance"}
          onClose={() => setPendingDecision(null)}
        >
          <p className="mb-3 text-xs text-[var(--muted)]">
            {pendingDecision === "approve"
              ? `Mark ${selected.studentName} as present for ${selected.courseCode}.`
              : `Mark ${selected.studentName} as absent for ${selected.courseCode}.`}
          </p>
          <label className="mb-1 block text-xs font-semibold" htmlFor="review-reason">
            Reason
          </label>
          <textarea
            id="review-reason"
            required
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="mb-2 w-full border border-[#c7cfd6] p-2 text-xs"
            placeholder="Explain the decision for the audit log"
          />
          {submitError ? <p className="mb-2 text-xs text-[var(--danger)]">{submitError}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="default" onClick={() => setPendingDecision(null)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              variant={pendingDecision === "approve" ? "primary" : "danger"}
              disabled={!reason.trim() || isSubmitting}
              onClick={() => resolveSelected(pendingDecision)}
            >
              {isSubmitting ? "Submitting..." : pendingDecision === "approve" ? "Approve" : "Reject"}
            </Button>
          </div>
        </Dialog>
      ) : null}

      <ConfirmationDialog
        open={pendingDecision === "retry"}
        title="Request retry"
        description={selected ? `Ask ${selected.studentName} to resubmit verification for ${selected.courseCode}.` : ""}
        confirmLabel={isSubmitting ? "Submitting..." : "Request retry"}
        onConfirm={() => resolveSelected("retry")}
        onCancel={() => setPendingDecision(null)}
        busy={isSubmitting}
      />
      <ConfirmationDialog
        open={pendingDecision === "escalate"}
        title="Escalate case"
        description={selected ? `Escalate ${selected.studentName}'s case to an administrator.` : ""}
        confirmLabel={isSubmitting ? "Submitting..." : "Escalate"}
        onConfirm={() => resolveSelected("escalate")}
        onCancel={() => setPendingDecision(null)}
        busy={isSubmitting}
      />
    </Card>
  );
}
