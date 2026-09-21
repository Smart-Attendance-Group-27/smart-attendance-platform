"use server";

import { revalidatePath } from "next/cache";
import { putAttendancePolicy } from "@/lib/api/admin";
import type { ApiAttendancePolicyWrite } from "@/lib/api/admin";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { isWebMockMode } from "@/lib/api/mode";

export type SaveAttendancePolicyResult = { ok: true } | { ok: false; error: string };

export async function saveAttendancePolicy(input: ApiAttendancePolicyWrite): Promise<SaveAttendancePolicyResult> {
  if (isWebMockMode()) return { ok: false, error: "Mock preview is read-only." };
  if (!input || !Number.isInteger(input.checkInWindowMinutes)
    || input.checkInWindowMinutes < 1 || input.checkInWindowMinutes > 180
    || !Number.isInteger(input.lateThresholdMinutes)
    || input.lateThresholdMinutes < 0 || input.lateThresholdMinutes > input.checkInWindowMinutes
    || !Number.isInteger(input.qrDefaultValidityMinutes)
    || input.qrDefaultValidityMinutes < 1 || input.qrDefaultValidityMinutes > 60
    || !Number.isInteger(input.faceConfidenceThresholdPercent)
    || input.faceConfidenceThresholdPercent < 50 || input.faceConfidenceThresholdPercent > 99) {
    return { ok: false, error: "Enter valid policy values. Late threshold cannot exceed the check-in window." };
  }
  try {
    await putAttendancePolicy(input);
    revalidatePath("/admin/policies");
    revalidatePath("/admin/dashboard");
    return { ok: true };
  } catch (error) {
    if (error instanceof CoreBackendError && error.status === 422) {
      return { ok: false, error: "Enter valid policy values. Late threshold cannot exceed the check-in window." };
    }
    return { ok: false, error: "Couldn't save attendance policy. Please try again." };
  }
}
