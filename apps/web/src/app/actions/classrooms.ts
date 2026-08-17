"use server";

import { revalidatePath } from "next/cache";
import { createClassroom, updateClassroom } from "@/lib/api/admin";

export type ClassroomFormPayload = {
  buildingId: string;
  classroomCode: string;
  floorNumber: number | null;
  capacity: number | null;
  latitude: number;
  longitude: number;
  defaultGeofenceRadiusM: number;
  status: string;
};

export type SaveClassroomResult = { ok: true } | { ok: false; message: string };

export async function saveClassroom(
  classroomId: string | null,
  payload: ClassroomFormPayload,
): Promise<SaveClassroomResult> {
  try {
    if (classroomId) {
      await updateClassroom(classroomId, payload);
    } else {
      await createClassroom(payload);
    }
  } catch {
    return { ok: false, message: "Couldn't save this classroom. Please try again." };
  }

  revalidatePath("/admin/classrooms");
  revalidatePath("/admin/dashboard");
  return { ok: true };
}
