"use server";

import { revalidatePath } from "next/cache";
import { CoreBackendError } from "@/lib/api/coreBackend";
import { submitLecturerCorrectionRequest } from "@/lib/api/lecturer";
import {
  CORRECTION_CATEGORIES,
  CORRECTION_DESCRIPTION_MAX,
  CORRECTION_DESCRIPTION_MIN,
  type CorrectionCategory,
  type CorrectionRequestType,
} from "@/lib/correctionRequests";

export type SubmitCorrectionInput = {
  requestType: CorrectionRequestType;
  category: CorrectionCategory;
  courseOfferingId?: string;
  timetableEntryId?: string;
  description: string;
};

export type SubmitCorrectionResult = { ok: true } | { ok: false; error: string };

export async function submitCorrectionRequest(
  input: SubmitCorrectionInput,
): Promise<SubmitCorrectionResult> {
  const description = input.description.trim();
  if (description.length < CORRECTION_DESCRIPTION_MIN || description.length > CORRECTION_DESCRIPTION_MAX) {
    return {
      ok: false,
      error: `Description must be between ${CORRECTION_DESCRIPTION_MIN} and ${CORRECTION_DESCRIPTION_MAX} characters.`,
    };
  }
  if (!CORRECTION_CATEGORIES[input.requestType]?.some((option) => option.value === input.category)) {
    return { ok: false, error: "Choose what needs correcting." };
  }
  if (input.requestType === "course_data" && !input.courseOfferingId) {
    return { ok: false, error: "Select the course." };
  }
  if (input.requestType === "timetable" && !input.timetableEntryId) {
    return { ok: false, error: "Select the timetable entry." };
  }

  try {
    await submitLecturerCorrectionRequest({
      requestType: input.requestType,
      category: input.category,
      courseOfferingId: input.requestType === "course_data" ? input.courseOfferingId : undefined,
      timetableEntryId: input.requestType === "timetable" ? input.timetableEntryId : undefined,
      description,
    });
    revalidatePath("/lecturer/courses");
    return { ok: true };
  } catch (error) {
    if (error instanceof CoreBackendError && error.status < 500) {
      return { ok: false, error: error.message };
    }
    return { ok: false, error: "Couldn't submit the request. Please try again." };
  }
}
