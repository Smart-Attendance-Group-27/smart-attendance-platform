import { courseStatusDisplay } from "@/lib/status";
import { toCsv } from "@/lib/csv";
import { CourseStatus, LecturerCourse } from "@/types/lecturer";

export type CourseFilters = {
  query: string;
  status: CourseStatus | "all";
};

export function courseStatusOptions(courses: LecturerCourse[]): string[] {
  return [...new Set(courses.map((course) => course.status))].sort();
}

export const EMPTY_COURSE_FILTERS: CourseFilters = { query: "", status: "all" };

export function filterCourses(courses: LecturerCourse[], filters: CourseFilters): LecturerCourse[] {
  const query = filters.query.trim().toLowerCase();
  return courses.filter((course) => {
    if (filters.status !== "all" && course.status !== filters.status) return false;
    if (!query) return true;
    return (
      course.courseCode.toLowerCase().includes(query) ||
      course.courseName.toLowerCase().includes(query)
    );
  });
}

export function coursesToCsv(courses: LecturerCourse[]): string {
  return toCsv(
    ["Course code", "Course name", "Lecturer", "Enrolled", "Attendance (%)", "Status"],
    courses.map((course) => [
      course.courseCode,
      course.courseName,
      course.lecturerName,
      course.enrolledCount,
      course.attendanceRatePercent,
      courseStatusDisplay(course.status).label,
    ]),
  );
}
