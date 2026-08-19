"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ConfirmationDialog } from "@/components/ui/Dialog";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { activateSession, closeSession } from "@/app/actions/sessions";
import { SessionStatus } from "@/types/lecturer";

const ACTIVATE_DESCRIPTION =
  "This opens check-in for enrolled students immediately. Eligible students will see this session as active on their app.";
const CLOSE_DESCRIPTION =
  "This ends check-in for this session. Students who haven't checked in yet will no longer be able to.";

export function SessionLifecycleControls({ sessionId, status }: { sessionId: string; status: SessionStatus }) {
  const router = useRouter();
  const [pendingAction, setPendingAction] = useState<"activate" | "close" | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openConfirm(action: "activate" | "close") {
    setError(null);
    setPendingAction(action);
  }

  function cancel() {
    if (isSubmitting) return;
    setPendingAction(null);
    setError(null);
  }

  async function confirm() {
    if (!pendingAction) return;
    setIsSubmitting(true);
    setError(null);
    const result = pendingAction === "activate" ? await activateSession(sessionId) : await closeSession(sessionId);
    setIsSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }
    setPendingAction(null);
    router.refresh();
  }

  if (status === "closed" || status === "cancelled") {
    return <StatusBadge tone="neutral">{status === "cancelled" ? "Session cancelled" : "Session closed"}</StatusBadge>;
  }

  return (
    <>
      {status === "scheduled" ? (
        <Button variant="primary" onClick={() => openConfirm("activate")}>
          Activate session
        </Button>
      ) : (
        <Button variant="danger" onClick={() => openConfirm("close")}>
          Close session
        </Button>
      )}

      <ConfirmationDialog
        open={pendingAction === "activate"}
        title="Activate session"
        description={error ?? ACTIVATE_DESCRIPTION}
        confirmLabel={isSubmitting ? "Activating..." : "Activate"}
        onConfirm={confirm}
        onCancel={cancel}
        busy={isSubmitting}
      />
      <ConfirmationDialog
        open={pendingAction === "close"}
        title="Close session"
        description={error ?? CLOSE_DESCRIPTION}
        confirmLabel={isSubmitting ? "Closing..." : "Close session"}
        onConfirm={confirm}
        onCancel={cancel}
        danger
        busy={isSubmitting}
      />
    </>
  );
}
