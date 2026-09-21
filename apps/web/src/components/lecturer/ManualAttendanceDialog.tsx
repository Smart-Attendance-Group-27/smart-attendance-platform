"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setStudentAttendance } from "@/app/actions/attendance";
import type { ApiManualAttendanceStatus } from "@/lib/api/lecturer";
import type { LiveSessionStudentRow } from "@/types/lecturer";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";

type Props = { sessionId: string; student: LiveSessionStudentRow };

export function ManualAttendanceDialog({ sessionId, student }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<ApiManualAttendanceStatus | "">("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function show() {
    setStatus(student.finalStatus ?? "");
    setReason(student.recordSource === "manual" ? student.manualReason ?? "" : "");
    setError(null);
    setOpen(true);
  }

  function close() {
    if (busy) return;
    setOpen(false);
    setError(null);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!status) {
      setError("Choose Present, Late, or Absent.");
      return;
    }
    const trimmedReason = reason.trim();
    if (trimmedReason.length < 3 || trimmedReason.length > 500) {
      setError("Reason must be between 3 and 500 characters.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const result = await setStudentAttendance(sessionId, student.studentId, {
        status, reason: trimmedReason,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Couldn't save attendance. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button onClick={show}>
        {student.finalStatus ? "Change attendance" : "Set attendance"}
      </Button>
      {open ? (
        <Dialog open title={`Manual attendance · ${student.fullName}`} onClose={close}>
          <form onSubmit={(event) => { void submit(event); }} className="space-y-4">
            <p className="text-xs text-[var(--muted)]">
              {student.studentIndex} · Choose the final result and record why it was set manually.
            </p>
            {student.finalStatus ? (
              <p className="text-xs text-[var(--muted)]">
                Current result: <strong className="capitalize">{student.finalStatus}</strong>
                {student.recordSource ? ` (${student.recordSource})` : ""}
              </p>
            ) : null}
            <FormField htmlFor={`manual-status-${student.studentId}`} label="Final attendance">
              <select
                id={`manual-status-${student.studentId}`}
                className={fieldInputClassName()}
                value={status}
                disabled={busy}
                onChange={(event) => setStatus(event.target.value as ApiManualAttendanceStatus | "")}
              >
                <option value="">Choose a result</option>
                <option value="present">Present</option>
                <option value="late">Late</option>
                <option value="absent">Absent</option>
              </select>
            </FormField>
            <FormField htmlFor={`manual-reason-${student.studentId}`} label="Reason" help="Required, 3–500 characters.">
              <textarea
                id={`manual-reason-${student.studentId}`}
                className={`${fieldInputClassName()} min-h-24 resize-y py-2`}
                maxLength={500}
                value={reason}
                disabled={busy}
                onChange={(event) => setReason(event.target.value)}
              />
            </FormField>
            {error ? <p role="alert" className="text-xs text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-2">
              <Button onClick={close} disabled={busy}>Cancel</Button>
              <Button type="submit" variant="primary" disabled={busy}>
                {busy ? "Saving..." : "Save attendance"}
              </Button>
            </div>
          </form>
        </Dialog>
      ) : null}
    </>
  );
}
