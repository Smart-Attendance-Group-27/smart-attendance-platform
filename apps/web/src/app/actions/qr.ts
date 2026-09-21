"use server";

import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { voidLecturerQrBatch } from "@/lib/api/lecturer";
import { isWebMockMode } from "@/lib/api/mode";

export type VoidQrBatchResult = { ok: true } | { ok: false; error: string };

export async function voidQrBatch(
  sessionId: string, qrSessionId: string, reason: string,
): Promise<VoidQrBatchResult> {
  if (isWebMockMode()) return { ok: false, error: "Mock preview is read-only." };
  if (!sessionId?.trim() || !qrSessionId?.trim()) {
    return { ok: false, error: "Choose a QR batch from this session." };
  }
  const trimmedReason = typeof reason === "string" ? reason.trim() : "";
  if (trimmedReason.length < 3 || trimmedReason.length > 500) {
    return { ok: false, error: "Reason must be between 3 and 500 characters." };
  }
  try {
    await voidLecturerQrBatch(sessionId, qrSessionId, trimmedReason);
    revalidatePath(`/lecturer/sessions/${sessionId}/qr`);
    revalidatePath(`/lecturer/sessions/${sessionId}`);
    return { ok: true };
  } catch (error) {
    if (error instanceof CoreBackendError) {
      if (error.status === 404) return { ok: false, error: "QR batch was not found in this session." };
      if (error.status === 409) return { ok: false, error: error.message };
      if (error.status === 422) return { ok: false, error: "Reason must be between 3 and 500 characters." };
    }
    return { ok: false, error: "Couldn't void the QR batch. Please try again." };
  }
}
