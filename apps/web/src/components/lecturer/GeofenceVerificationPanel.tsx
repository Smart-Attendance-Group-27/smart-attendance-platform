"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { waiveSessionGeofence } from "@/app/actions/sessions";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { Notice } from "@/components/ui/Notice";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { GEOFENCE_WAIVER_REASONS } from "@/lib/geofenceWaiver";
import type { SessionVerificationView } from "@/types/lecturer";

type Props = {
  sessionId: string;
  verification: SessionVerificationView;
  // Waiving is only offered while the session is active.
  canWaive: boolean;
};

export function GeofenceVerificationPanel({ sessionId, verification, canWaive }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reasonCode, setReasonCode] = useState("");
  const [reasonText, setReasonText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const { health, waiver } = verification;
  const waived = verification.geofence === "waived";

  function dismiss() {
    if (busy) return;
    setOpen(false);
    setReasonCode("");
    setReasonText("");
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reasonCode) {
      setError("Choose a reason.");
      return;
    }
    if (reasonCode === "OTHER" && !reasonText.trim()) {
      setError("Describe the reason when choosing Other.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await waiveSessionGeofence(sessionId, reasonCode, reasonText);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Couldn't waive the geofence requirement. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="geofence-verification-heading" className="border-b border-[var(--line)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="geofence-verification-heading" className="text-sm font-semibold text-[#2d3d49]">
            Geofence verification
          </h2>
          <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs">
            <div><dt className="inline text-[var(--muted)]">Attempts: </dt><dd className="inline font-semibold">{health.attempted}</dd></div>
            <div><dt className="inline text-[var(--muted)]">Passed: </dt><dd className="inline font-semibold">{health.passed}</dd></div>
            <div><dt className="inline text-[var(--muted)]">Failed: </dt><dd className="inline font-semibold">{health.failed}</dd></div>
            <div><dt className="inline text-[var(--muted)]">Failure rate: </dt><dd className="inline font-semibold">{health.failureRatePercent}%</dd></div>
          </dl>
          <p className="mt-1 text-[10px] text-[var(--muted)]">Counted per student.</p>
        </div>
        <div className="flex items-center gap-2">
          {waived
            ? <StatusBadge tone="warning">Requirement waived</StatusBadge>
            : <StatusBadge tone="info">Required</StatusBadge>}
          {!waived && canWaive ? (
            <Button variant="danger" onClick={() => setOpen(true)}>Waive Geofence Requirement</Button>
          ) : null}
        </div>
      </div>

      {!waived && health.warning ? (
        <div className="mt-3">
          <Notice variant="warning" title="Possible session-wide location verification problem detected.">
            {health.failed} of {health.attempted} students have not passed the location check.
            Check the room location and student devices before deciding whether to waive it.
          </Notice>
        </div>
      ) : null}

      {waived && waiver ? (
        <dl className="mt-3 grid grid-cols-1 gap-2 border border-[var(--line)] bg-[#fafbfc] p-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Waived by</dt><dd className="mt-1 font-semibold">{waiver.performedByName}</dd></div>
          <div><dt className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Time</dt><dd className="mt-1 font-semibold">{waiver.performedAtLabel}</dd></div>
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Reason</dt>
            <dd className="mt-1 font-semibold">{waiver.reasonLabel}</dd>
            {waiver.reasonText ? <dd className="mt-0.5 text-[var(--muted)]">{waiver.reasonText}</dd> : null}
          </div>
          <div><dt className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Students affected</dt><dd className="mt-1 font-semibold">{waiver.affectedStudentCount}</dd></div>
        </dl>
      ) : null}

      <Dialog open={open} title="Waive geofence verification?" onClose={dismiss}>
        <form onSubmit={submit}>
          <p className="text-xs leading-relaxed text-[var(--muted)]">
            This removes geofence verification as a requirement for this attendance session.
            Existing geofence results will not be modified.
          </p>
          <p className="mt-3 text-xs font-semibold">Students must still complete:</p>
          <ul className="mb-4 mt-1 list-disc pl-5 text-xs text-[var(--muted)]">
            <li>Face verification</li>
            <li>Any required QR verification</li>
          </ul>
          <div className="space-y-3">
            <FormField label="Reason" htmlFor={`geofence-waiver-reason-${sessionId}`}>
              <select
                id={`geofence-waiver-reason-${sessionId}`}
                required
                value={reasonCode}
                onChange={(event) => setReasonCode(event.target.value)}
                disabled={busy}
                className={fieldInputClassName()}
              >
                <option value="">Select a reason</option>
                {GEOFENCE_WAIVER_REASONS.map((reason) => (
                  <option key={reason.code} value={reason.code}>{reason.label}</option>
                ))}
              </select>
            </FormField>
            <FormField
              label={reasonCode === "OTHER" ? "Description" : "Additional note (optional)"}
              htmlFor={`geofence-waiver-note-${sessionId}`}
              help="Up to 500 characters"
            >
              <textarea
                id={`geofence-waiver-note-${sessionId}`}
                required={reasonCode === "OTHER"}
                maxLength={500}
                value={reasonText}
                onChange={(event) => setReasonText(event.target.value)}
                disabled={busy}
                className={`${fieldInputClassName()} min-h-20 py-2`}
              />
            </FormField>
          </div>
          {error ? <p role="alert" className="mt-2 text-xs text-[var(--danger)]">{error}</p> : null}
          <div className="mt-4 flex justify-end gap-2">
            <Button onClick={dismiss} disabled={busy}>Cancel</Button>
            <Button type="submit" variant="danger" disabled={busy}>
              {busy ? "Waiving..." : "Confirm Waiver"}
            </Button>
          </div>
        </form>
      </Dialog>
    </section>
  );
}
