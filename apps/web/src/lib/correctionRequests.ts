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
