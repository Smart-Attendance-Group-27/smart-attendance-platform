"use server";

import { revalidatePath } from "next/cache";
import {
  createCourse,
  createOffering,
  createTimetableEntry,
  deactivateTimetableEntry,
  dropStudent,
  enrolStudent,
  updateCourse,
  updateOffering,
  updateTimetableEntry,
  type ApiCourseWriteRequest,
  type ApiOfferingWriteRequest,
  type ApiTimetableWriteRequest,
} from "@/lib/api/admin";
import { CoreBackendError } from "@/lib/api/coreBackend";

export type AcademicActionResult = { ok: true } | { ok: false; message: string };

function failure(error: unknown, fallback: string): AcademicActionResult {
  return {
    ok: false,
    message: error instanceof CoreBackendError ? error.message : fallback,
  };
}

function refreshAcademicViews() {
  revalidatePath("/admin/academic");
  revalidatePath("/lecturer/dashboard");
}

export async function saveCourse(
  courseId: string | null,
  payload: ApiCourseWriteRequest,
): Promise<AcademicActionResult> {
  try {
    await (courseId ? updateCourse(courseId, payload) : createCourse(payload));
  } catch (error) {
    return failure(error, "Couldn't save this course. Please try again.");
  }
  refreshAcademicViews();
  return { ok: true };
}

export async function saveOffering(
  offeringId: string | null,
  payload: ApiOfferingWriteRequest,
): Promise<AcademicActionResult> {
  try {
    await (offeringId ? updateOffering(offeringId, payload) : createOffering(payload));
  } catch (error) {
    return failure(error, "Couldn't save this course offering. Please try again.");
  }
  refreshAcademicViews();
  return { ok: true };
}

export async function addEnrolment(
  offeringId: string,
  studentId: string,
): Promise<AcademicActionResult> {
  try {
    await enrolStudent(offeringId, studentId);
  } catch (error) {
    return failure(error, "Couldn't enrol this student. Please try again.");
  }
  refreshAcademicViews();
  return { ok: true };
}

export async function removeEnrolment(
  offeringId: string,
  studentId: string,
): Promise<AcademicActionResult> {
  try {
    await dropStudent(offeringId, studentId);
  } catch (error) {
    return failure(error, "Couldn't drop this enrolment. Please try again.");
  }
  refreshAcademicViews();
  return { ok: true };
}

export async function saveTimetableEntry(
  entryId: string | null,
  payload: ApiTimetableWriteRequest,
): Promise<AcademicActionResult> {
  try {
    await (entryId
      ? updateTimetableEntry(entryId, payload)
      : createTimetableEntry(payload));
  } catch (error) {
    return failure(error, "Couldn't save this timetable entry. Please try again.");
  }
  refreshAcademicViews();
  return { ok: true };
}

export async function removeTimetableEntry(entryId: string): Promise<AcademicActionResult> {
  try {
    await deactivateTimetableEntry(entryId);
  } catch (error) {
    return failure(error, "Couldn't deactivate this timetable entry. Please try again.");
  }
  refreshAcademicViews();
  return { ok: true };
}
