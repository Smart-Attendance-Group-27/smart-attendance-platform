"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { voidQrBatch } from "@/app/actions/qr";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";

export function VoidQrBatchButton({ sessionId, qrSessionId }: { sessionId: string; qrSessionId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function dismiss() {
    if (busy) return;
    setOpen(false);
    setReason("");
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await voidQrBatch(sessionId, qrSessionId, reason);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setNotice("QR batch voided.");
      setOpen(false);
      router.refresh();
    } catch {
      setError("Couldn't void the QR batch. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="danger" onClick={() => setOpen(true)}>Void batch</Button>
      {notice ? <span role="status" className="ml-2 text-green-700">{notice}</span> : null}
      <Dialog open={open} title="Void QR batch" onClose={dismiss}>
        <form onSubmit={submit}>
          <p className="mb-4 text-xs leading-relaxed text-[var(--muted)]">
            This batch will stop counting toward attendance for every student. Give a reason for the audit record.
          </p>
          <FormField label="Reason" htmlFor={`qr-void-reason-${qrSessionId}`} help="3 to 500 characters">
            <textarea
              id={`qr-void-reason-${qrSessionId}`} required minLength={3} maxLength={500}
              value={reason} onChange={(event) => setReason(event.target.value)}
              className={`${fieldInputClassName()} min-h-20 py-2`}
            />
          </FormField>
          {error ? <p role="alert" className="mt-2 text-xs text-[var(--danger)]">{error}</p> : null}
          <div className="mt-4 flex justify-end gap-2">
            <Button onClick={dismiss} disabled={busy}>Cancel</Button>
            <Button type="submit" variant="danger" disabled={busy}>
              {busy ? "Voiding..." : "Void batch"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
