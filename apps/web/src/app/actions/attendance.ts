"use server";

import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { isWebMockMode } from "@/lib/api/mode";
import { putManualAttendance } from "@/lib/api/lecturer";
import type { ApiManualAttendanceStatus } from "@/lib/api/lecturer";

export type ManualAttendanceInput = {
  status: ApiManualAttendanceStatus;
  reason: string;
};

export type ManualAttendanceActionResult =
  | { ok: true; status: ApiManualAttendanceStatus }
  | { ok: false; error: string };

export async function setStudentAttendance(
  sessionId: string,
  studentId: string,
  input: ManualAttendanceInput,
): Promise<ManualAttendanceActionResult> {
  if (isWebMockMode()) {
    return { ok: false, error: "Mock preview is read-only." };
  }
  if (!sessionId?.trim() || !studentId?.trim()) {
    return { ok: false, error: "Choose a student from an attendance session." };
  }
  if (!input || !["present", "late", "absent"].includes(input.status)) {
    return { ok: false, error: "Choose Present, Late, or Absent." };
  }
  const reason = typeof input.reason === "string" ? input.reason.trim() : "";
  if (reason.length < 3 || reason.length > 500) {
    return { ok: false, error: "Reason must be between 3 and 500 characters." };
  }

  try {
    const record = await putManualAttendance(sessionId.trim(), studentId.trim(), {
      status: input.status,
      reason,
    });
    revalidatePath(`/lecturer/sessions/${sessionId.trim()}`);
    revalidatePath("/lecturer/sessions");
    revalidatePath("/lecturer/dashboard");
    revalidatePath("/lecturer/review");
    return { ok: true, status: record.status };
  } catch (error) {
    if (error instanceof CoreBackendError) {
      if (error.status === 404) return { ok: false, error: "Session or student was not found. Refresh and try again." };
      if (error.status === 409) return { ok: false, error: "Attendance cannot be changed before the session starts or after cancellation." };
      if (error.status === 403) return { ok: false, error: "You cannot change attendance for this session." };
      if (error.status === 422) return { ok: false, error: "Choose a valid status and a reason between 3 and 500 characters." };
    }
    return { ok: false, error: "Couldn't save attendance. Please try again." };
  }
}
