"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ConfirmationDialog, Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FinalizationSummary } from "@/components/lecturer/FinalizationSummary";
import { activateSession, cancelSession, closeSession } from "@/app/actions/sessions";
import type { ApiFinalizationSummary } from "@/lib/api/lecturer";
import type { SessionStatus } from "@/types/lecturer";

const ACTIVATE_DESCRIPTION =
  "This opens check-in for enrolled students immediately. Eligible students will see this session as active on their app.";
const CLOSE_DESCRIPTION =
  "This ends check-in for this session and finalizes attendance when available. Students who haven't checked in yet will no longer be able to.";

export function SessionLifecycleControls({ sessionId, status }: { sessionId: string; status: SessionStatus }) {
  const router = useRouter();
  const [pendingAction, setPendingAction] = useState<"activate" | "close" | "cancel" | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [closeSummary, setCloseSummary] = useState<ApiFinalizationSummary | null>(null);
  const [showCloseSummary, setShowCloseSummary] = useState(false);

  function openConfirm(action: "activate" | "close" | "cancel") {
    setError(null);
    setReason("");
    setPendingAction(action);
  }

  function dismiss() {
    if (isSubmitting) return;
    setPendingAction(null);
    setError(null);
  }

  async function confirm() {
    if (pendingAction !== "activate" && pendingAction !== "close") return;
    setIsSubmitting(true);
    setError(null);
    try {
      if (pendingAction === "activate") {
        const result = await activateSession(sessionId);
        if (!result.ok) {
          setError(result.error);
          return;
        }
      } else {
        const result = await closeSession(sessionId);
        if (!result.ok) {
          setError(result.error);
          return;
        }
        setCloseSummary(result.finalization);
        setShowCloseSummary(true);
      }
      setPendingAction(null);
      router.refresh();
    } catch {
      setError("Couldn't update the session. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitCancellation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingAction !== "cancel") return;
    const trimmedReason = reason.trim();
    if (trimmedReason.length < 3 || trimmedReason.length > 500) {
      setError("Reason must be between 3 and 500 characters.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await cancelSession(sessionId, trimmedReason);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setPendingAction(null);
      router.refresh();
    } catch {
      setError("Couldn't cancel the session. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {status === "scheduled" ? (
          <Button variant="primary" onClick={() => openConfirm("activate")}>Activate session</Button>
        ) : status === "in_progress" ? (
          <Button variant="danger" onClick={() => openConfirm("close")}>Close session</Button>
        ) : (
          <StatusBadge tone={status === "cancelled" ? "danger" : "neutral"}>
            {status === "cancelled" ? "Session cancelled" : "Session closed"}
          </StatusBadge>
        )}
        {(status === "scheduled" || status === "in_progress") && (
          <Button variant="danger" onClick={() => openConfirm("cancel")}>Cancel session</Button>
        )}
      </div>

      <ConfirmationDialog
        open={pendingAction === "activate"}
        title="Activate session"
        description={error ?? ACTIVATE_DESCRIPTION}
        confirmLabel={isSubmitting ? "Activating..." : "Activate"}
        onConfirm={confirm}
        onCancel={dismiss}
        busy={isSubmitting}
      />
      <ConfirmationDialog
        open={pendingAction === "close"}
        title="Close session"
        description={error ?? CLOSE_DESCRIPTION}
        confirmLabel={isSubmitting ? "Closing..." : "Close session"}
        onConfirm={confirm}
        onCancel={dismiss}
        danger
        busy={isSubmitting}
      />
      <Dialog open={pendingAction === "cancel"} title="Cancel session" onClose={dismiss}>
        <form onSubmit={submitCancellation}>
          <p className="mb-4 text-xs leading-relaxed text-[var(--muted)]">
            Cancellation ends this session without finalizing attendance. Give a reason for the record.
          </p>
          <FormField label="Reason" htmlFor="session-cancellation-reason" help="3 to 500 characters">
            <textarea
              id="session-cancellation-reason"
              className={`${fieldInputClassName()} min-h-24 py-2`}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={500}
              disabled={isSubmitting}
              required
            />
          </FormField>
          {error ? <p role="alert" className="mt-2 text-xs text-[var(--danger)]">{error}</p> : null}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="default" onClick={dismiss} disabled={isSubmitting}>Keep session</Button>
            <Button variant="danger" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Cancelling..." : "Cancel session"}
            </Button>
          </div>
        </form>
      </Dialog>
      <Dialog open={showCloseSummary} title="Session closed" onClose={() => setShowCloseSummary(false)}>
        <FinalizationSummary summary={closeSummary} />
        <div className="mt-4 flex justify-end">
          <Button onClick={() => setShowCloseSummary(false)}>Done</Button>
        </div>
      </Dialog>
    </>
  );
}
