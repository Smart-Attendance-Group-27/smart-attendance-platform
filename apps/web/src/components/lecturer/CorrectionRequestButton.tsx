"use client";

import { FormEvent, useState } from "react";
import { submitCorrectionRequest } from "@/app/actions/corrections";
import { Button, ButtonVariant } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import {
  CORRECTION_CATEGORIES,
  CORRECTION_DESCRIPTION_MAX,
  CORRECTION_DESCRIPTION_MIN,
  CorrectionCategory,
  CorrectionRequestType,
} from "@/lib/correctionRequests";

export type CorrectionTargetOption = { id: string; label: string };

type Props = {
  requestType: CorrectionRequestType;
  buttonLabel: string;
  dialogTitle: string;
  targetLabel: string;
  targets: CorrectionTargetOption[];
  variant?: ButtonVariant;
};

export function CorrectionRequestButton({
  requestType,
  buttonLabel,
  dialogTitle,
  targetLabel,
  targets,
  variant = "default",
}: Props) {
  const [open, setOpen] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [category, setCategory] = useState<CorrectionCategory | "">("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const idPrefix = `correction-${requestType}`;

  function show() {
    setTargetId("");
    setCategory("");
    setDescription("");
    setError(null);
    setSubmitted(false);
    setOpen(true);
  }

  function close() {
    if (busy) return;
    setOpen(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!targetId) {
      setError(`Select the ${targetLabel.toLowerCase()}.`);
      return;
    }
    if (!category) {
      setError("Choose what needs correcting.");
      return;
    }
    const trimmed = description.trim();
    if (trimmed.length < CORRECTION_DESCRIPTION_MIN || trimmed.length > CORRECTION_DESCRIPTION_MAX) {
      setError(
        `Describe the correction in ${CORRECTION_DESCRIPTION_MIN}–${CORRECTION_DESCRIPTION_MAX} characters.`,
      );
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const result = await submitCorrectionRequest({
        requestType,
        category,
        courseOfferingId: requestType === "course_data" ? targetId : undefined,
        timetableEntryId: requestType === "timetable" ? targetId : undefined,
        description: trimmed,
      });
      if (result.ok) setSubmitted(true);
      else setError(result.error);
    } catch {
      setError("Couldn't submit the request. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button
        variant={variant}
        onClick={show}
        disabled={targets.length === 0}
        title={targets.length === 0 ? "Nothing is assigned to your account yet." : undefined}
      >
        {buttonLabel}
      </Button>
      {open ? (
        <Dialog open title={dialogTitle} onClose={close}>
          {submitted ? (
            <div className="space-y-4">
              <p role="status" className="text-xs">
                Your request was submitted for administrative review. The academic record has not
                been changed.
              </p>
              <div className="flex justify-end">
                <Button variant="primary" onClick={close}>
                  Close
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={(event) => { void submit(event); }} className="space-y-4">
              <p className="text-xs text-[var(--muted)]">
                Academic records are read-only. Describe what is wrong and an administrator will
                review it.
              </p>
              <FormField htmlFor={`${idPrefix}-target`} label={targetLabel}>
                <select
                  id={`${idPrefix}-target`}
                  className={fieldInputClassName()}
                  value={targetId}
                  disabled={busy}
                  onChange={(event) => setTargetId(event.target.value)}
                >
                  <option value="">Choose one</option>
                  {targets.map((target) => (
                    <option key={target.id} value={target.id}>
                      {target.label}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField htmlFor={`${idPrefix}-category`} label="What needs correcting">
                <select
                  id={`${idPrefix}-category`}
                  className={fieldInputClassName()}
                  value={category}
                  disabled={busy}
                  onChange={(event) => setCategory(event.target.value as CorrectionCategory | "")}
                >
                  <option value="">Choose one</option>
                  {CORRECTION_CATEGORIES[requestType].map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField
                htmlFor={`${idPrefix}-description`}
                label="Details"
                help={`Required, ${CORRECTION_DESCRIPTION_MIN}–${CORRECTION_DESCRIPTION_MAX} characters.`}
              >
                <textarea
                  id={`${idPrefix}-description`}
                  className={`${fieldInputClassName()} min-h-24 resize-y py-2`}
                  maxLength={CORRECTION_DESCRIPTION_MAX}
                  value={description}
                  disabled={busy}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </FormField>
              {error ? <p role="alert" className="text-xs text-[var(--danger)]">{error}</p> : null}
              <div className="flex justify-end gap-2">
                <Button onClick={close} disabled={busy}>Cancel</Button>
                <Button type="submit" variant="primary" disabled={busy}>
                  {busy ? "Submitting..." : "Submit request"}
                </Button>
              </div>
            </form>
          )}
        </Dialog>
      ) : null}
    </>
  );
}
