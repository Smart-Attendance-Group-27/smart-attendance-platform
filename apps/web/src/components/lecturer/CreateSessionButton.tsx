"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { createSession } from "@/app/actions/sessions";
import { TimetableOption } from "@/types/lecturer";

// <input type="datetime-local"> values have no timezone — they represent
// whatever the browser's local clock shows, which is what we want since the
// lecturer picks a time on their own device.
function toDateTimeLocalValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function defaultStartValue(): string {
  return toDateTimeLocalValue(new Date());
}

function defaultEndValue(startValue: string): string {
  const start = new Date(startValue);
  return toDateTimeLocalValue(new Date(start.getTime() + 60 * 60_000));
}

export function CreateSessionButton({ timetableOptions }: { timetableOptions: TimetableOption[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [timetableEntryId, setTimetableEntryId] = useState(timetableOptions[0]?.id ?? "");
  const [sessionTitle, setSessionTitle] = useState("");
  const [scheduledStartAt, setScheduledStartAt] = useState(defaultStartValue);
  const [scheduledEndAt, setScheduledEndAt] = useState(() => defaultEndValue(defaultStartValue()));
  const [requiresFaceVerification, setRequiresFaceVerification] = useState(true);
  const [requiresGeofence, setRequiresGeofence] = useState(true);
  const [requiresQr, setRequiresQr] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function close() {
    if (isSubmitting) return;
    setOpen(false);
    setSubmitError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!timetableEntryId) {
      setSubmitError("Select a timetable slot.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    // Resolve the naive datetime-local values ("2026-08-19T17:41", no
    // timezone) to real ISO instants here, in the browser — this is the only
    // place that actually knows the lecturer's local timezone. A server
    // action runs inside the backend's own timezone (UTC in Docker), so
    // sending the naive string across and parsing it there would silently
    // reinterpret the wall-clock time as UTC.
    const result = await createSession({
      timetableEntryId,
      sessionTitle: sessionTitle.trim(),
      scheduledStartAt: new Date(scheduledStartAt).toISOString(),
      scheduledEndAt: new Date(scheduledEndAt).toISOString(),
      requiresFaceVerification,
      requiresGeofence,
      requiresQr,
    });
    setIsSubmitting(false);

    if (!result.ok) {
      setSubmitError(result.error);
      return;
    }

    setOpen(false);
    setSessionTitle("");
    router.refresh();
  }

  if (timetableOptions.length === 0) {
    return (
      <Button disabled title="No timetable slots are assigned to your account yet.">
        Create session
      </Button>
    );
  }

  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>
        Create session
      </Button>
      <Dialog open={open} title="Create attendance session" onClose={close}>
        <form className="grid gap-3" onSubmit={handleSubmit}>
          <FormField label="Timetable slot" htmlFor="create-session-timetable-entry">
            <select
              id="create-session-timetable-entry"
              className={fieldInputClassName()}
              value={timetableEntryId}
              onChange={(event) => setTimetableEntryId(event.target.value)}
              required
            >
              {timetableOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Session title" htmlFor="create-session-title" help="Shown to you and to enrolled students.">
            <input
              id="create-session-title"
              className={fieldInputClassName()}
              value={sessionTitle}
              onChange={(event) => setSessionTitle(event.target.value)}
              placeholder="e.g. Week 6 Lecture"
              required
            />
          </FormField>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Starts" htmlFor="create-session-start">
              <input
                id="create-session-start"
                type="datetime-local"
                className={fieldInputClassName()}
                value={scheduledStartAt}
                onChange={(event) => setScheduledStartAt(event.target.value)}
                required
              />
            </FormField>
            <FormField label="Ends" htmlFor="create-session-end">
              <input
                id="create-session-end"
                type="datetime-local"
                className={fieldInputClassName()}
                value={scheduledEndAt}
                onChange={(event) => setScheduledEndAt(event.target.value)}
                required
              />
            </FormField>
          </div>

          <FormField label="Verification requirements" htmlFor="create-session-requirements">
            <div id="create-session-requirements" className="flex flex-col gap-1.5 text-xs">
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={requiresFaceVerification}
                  onChange={(event) => setRequiresFaceVerification(event.target.checked)}
                />
                Require face verification
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={requiresGeofence}
                  onChange={(event) => setRequiresGeofence(event.target.checked)}
                />
                Require geofence check
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={requiresQr}
                  onChange={(event) => setRequiresQr(event.target.checked)}
                />
                Require QR verification
              </label>
            </div>
          </FormField>

          {submitError ? <p className="text-xs text-[var(--danger)]">{submitError}</p> : null}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="default" onClick={close} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={isSubmitting}>
              {isSubmitting ? "Creating..." : "Create session"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
