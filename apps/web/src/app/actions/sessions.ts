"use server";

import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { activateLecturerSession, closeLecturerSession, createLecturerSession } from "@/lib/api/lecturer";

export type CreateSessionInput = {
  timetableEntryId: string;
  sessionTitle: string;
  // Real ISO instants (e.g. "2026-08-19T12:11:00.000Z") — the caller must
  // resolve these from the lecturer's browser-local time before invoking this
  // action. A server action runs in the backend's own timezone, so a naive
  // "no timezone" string parsed here would silently be misinterpreted.
  scheduledStartAt: string;
  scheduledEndAt: string;
  requiresFaceVerification: boolean;
  requiresGeofence: boolean;
  requiresQr: boolean;
};

export type CreateSessionResult = { ok: true; sessionId: string } | { ok: false; error: string };

export async function createSession(input: CreateSessionInput): Promise<CreateSessionResult> {
  const startDate = new Date(input.scheduledStartAt);
  const endDate = new Date(input.scheduledEndAt);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return { ok: false, error: "Enter a valid start and end time." };
  }

  try {
    const created = await createLecturerSession({
      timetableEntryId: input.timetableEntryId,
      sessionTitle: input.sessionTitle,
      scheduledStartAt: startDate.toISOString(),
      scheduledEndAt: endDate.toISOString(),
      requiresFaceVerification: input.requiresFaceVerification,
      requiresGeofence: input.requiresGeofence,
      requiresQr: input.requiresQr,
    });
    revalidatePath("/lecturer/sessions");
    revalidatePath("/lecturer/dashboard");
    return { ok: true, sessionId: created.id };
  } catch (error) {
    if (error instanceof CoreBackendError && error.status < 500) {
      return { ok: false, error: error.message };
    }
    return { ok: false, error: "Couldn't create the session. Please try again." };
  }
}

export type SessionLifecycleResult = { ok: true } | { ok: false; error: string };

export async function activateSession(sessionId: string): Promise<SessionLifecycleResult> {
  try {
    await activateLecturerSession(sessionId);
    revalidatePath("/lecturer/sessions");
    revalidatePath(`/lecturer/sessions/${sessionId}`);
    revalidatePath("/lecturer/dashboard");
    return { ok: true };
  } catch (error) {
    if (error instanceof CoreBackendError && error.status < 500) {
      return { ok: false, error: error.message };
    }
    return { ok: false, error: "Couldn't activate the session. Please try again." };
  }
}

export async function closeSession(sessionId: string): Promise<SessionLifecycleResult> {
  try {
    await closeLecturerSession(sessionId);
    revalidatePath("/lecturer/sessions");
    revalidatePath(`/lecturer/sessions/${sessionId}`);
    revalidatePath("/lecturer/dashboard");
    return { ok: true };
  } catch (error) {
    if (error instanceof CoreBackendError && error.status < 500) {
      return { ok: false, error: error.message };
    }
    return { ok: false, error: "Couldn't close the session. Please try again." };
  }
}
