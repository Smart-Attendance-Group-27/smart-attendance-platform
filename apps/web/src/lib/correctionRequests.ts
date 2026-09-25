export type CorrectionRequestType = "course_data" | "timetable";

export type CorrectionCategory =
  | "course_details"
  | "enrolment"
  | "lecturer_assignment"
  | "timetable_day_time"
  | "timetable_room"
  | "timetable_missing"
  | "other";

export const CORRECTION_CATEGORIES: Record<
  CorrectionRequestType,
  { value: CorrectionCategory; label: string }[]
> = {
  course_data: [
    { value: "course_details", label: "Course name or details" },
    { value: "enrolment", label: "Enrolment or student list" },
    { value: "lecturer_assignment", label: "Lecturer assignment" },
    { value: "other", label: "Other" },
  ],
  timetable: [
    { value: "timetable_day_time", label: "Wrong day or time" },
    { value: "timetable_room", label: "Wrong room" },
    { value: "timetable_missing", label: "Entry missing or should be removed" },
    { value: "other", label: "Other" },
  ],
};

export const CORRECTION_DESCRIPTION_MIN = 10;
export const CORRECTION_DESCRIPTION_MAX = 1000;

export type CorrectionRequestStatus = "pending" | "approved" | "rejected" | "resolved";
export type CorrectionDecision = "approved" | "rejected" | "resolved";

export function correctionCategoryLabel(category: string): string {
  const all = [...CORRECTION_CATEGORIES.course_data, ...CORRECTION_CATEGORIES.timetable];
  return all.find((option) => option.value === category)?.label ?? category;
}

// What the review tables show for one request; built on the server.
export type CorrectionRequestRow = {
  id: string;
  requestType: CorrectionRequestType;
  typeLabel: string;
  categoryLabel: string;
  courseLabel: string;
  // The timetable entry a timetable request is about, otherwise a dash.
  targetLabel: string;
  requesterName: string;
  description: string;
  status: string;
  reviewNote: string | null;
  createdLabel: string;
  reviewedLabel: string | null;
};

// The next decisions an administrator may take, mirroring the backend rules.
export function allowedDecisions(status: string): CorrectionDecision[] {
  if (status === "pending") return ["approved", "rejected"];
  if (status === "approved") return ["resolved"];
  return [];
}
