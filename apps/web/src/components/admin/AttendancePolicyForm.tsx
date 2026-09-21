"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { saveAttendancePolicy } from "@/app/actions/policies";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import type { AttendancePolicy } from "@/types/admin";

type PolicyValues = Pick<AttendancePolicy, "checkInWindowMinutes" | "lateThresholdMinutes" | "qrDefaultValidityMinutes" | "faceConfidenceThresholdPercent">;

export function AttendancePolicyForm({ policy, readOnly = false }: { policy: AttendancePolicy; readOnly?: boolean }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [values, setValues] = useState<PolicyValues>({
    checkInWindowMinutes: policy.checkInWindowMinutes,
    lateThresholdMinutes: policy.lateThresholdMinutes,
    qrDefaultValidityMinutes: policy.qrDefaultValidityMinutes,
    faceConfidenceThresholdPercent: policy.faceConfidenceThresholdPercent,
  });
  const [feedback, setFeedback] = useState<{ error?: string; success?: string }>({});

  const fields: { key: keyof PolicyValues; label: string; help: string; min: number; max: number }[] = [
    { key: "checkInWindowMinutes", label: "Check-in window (minutes)", help: "Time allowed for initial face and location verification.", min: 1, max: 180 },
    { key: "lateThresholdMinutes", label: "Late threshold (minutes)", help: "Cannot exceed the check-in window.", min: 0, max: 180 },
    { key: "faceConfidenceThresholdPercent", label: "Face confidence threshold (%)", help: "Submissions below this percentage enter the review queue.", min: 50, max: 99 },
    { key: "qrDefaultValidityMinutes", label: "Default QR validity (minutes)", help: "Used when a lecturer does not set a QR validity explicitly.", min: 1, max: 60 },
  ];

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback({});
    startTransition(async () => {
      const result = await saveAttendancePolicy(values);
      if (result.ok) {
        setFeedback({ success: "Attendance policy saved." });
        router.refresh();
      } else {
        setFeedback({ error: result.error });
      }
    });
  }

  return (
    <Card title="Default attendance and verification policy" className="border-l-4 border-l-[var(--uom-gold)]">
      <form onSubmit={submit}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {fields.map((field) => (
            <FormField key={field.key} label={field.label} htmlFor={field.key} help={field.help}>
              <input
                id={field.key} type="number" min={field.min} max={field.max} step="1" required
                disabled={readOnly || pending}
                value={values[field.key]}
                onChange={(event) => {
                  setFeedback({});
                  setValues((current) => ({ ...current, [field.key]: Number(event.target.value) }));
                }}
                className={fieldInputClassName()}
              />
            </FormField>
          ))}
        </div>
        {!readOnly ? (
          <div className="mt-4 flex items-center gap-3">
            <Button type="submit" variant="primary" disabled={pending}>{pending ? "Saving…" : "Save changes"}</Button>
            {feedback.error ? <p role="alert" className="text-xs text-[var(--danger)]">{feedback.error}</p> : null}
            {feedback.success ? <p role="status" className="text-xs text-green-700">{feedback.success}</p> : null}
          </div>
        ) : null}
      </form>
    </Card>
  );
}
