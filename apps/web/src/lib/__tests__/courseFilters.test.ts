import { describe, expect, it } from "vitest";
import { toCsv } from "@/lib/csv";
import { coursesToCsv, filterCourses } from "@/lib/courseFilters";
import { LecturerCourse } from "@/types/lecturer";

const courses: LecturerCourse[] = [
  {
    courseId: "1",
    courseCode: "CS3203",
    courseName: "Software Engineering, Project",
    scheduleSummary: "",
    lecturerName: "N. Perera",
    enrolledCount: 40,
    attendanceRatePercent: 82.5,
    status: "active",
  },
  {
    courseId: "2",
    courseCode: "CS6101",
    courseName: 'Advanced "Databases"',
    scheduleSummary: "",
    lecturerName: "N. Perera",
    enrolledCount: 12,
    attendanceRatePercent: 70,
    status: "correction_needed",
  },
];

describe("filterCourses", () => {
  it("returns everything with empty filters", () => {
    expect(filterCourses(courses, { query: "", status: "all" })).toHaveLength(2);
  });

  it("matches code or name case-insensitively", () => {
    expect(filterCourses(courses, { query: " cs61 ", status: "all" }).map((c) => c.courseId)).toEqual(["2"]);
    expect(filterCourses(courses, { query: "software", status: "all" }).map((c) => c.courseId)).toEqual(["1"]);
  });

  it("combines search and status", () => {
    expect(filterCourses(courses, { query: "cs", status: "active" }).map((c) => c.courseId)).toEqual(["1"]);
    expect(filterCourses(courses, { query: "cs61", status: "active" })).toEqual([]);
  });
});

describe("toCsv", () => {
  it("escapes commas, quotes and newlines", () => {
    expect(toCsv(["a", "b"], [["x,y", 'say "hi"'], ["line\nbreak", 3]])).toBe(
      'a,b\r\n"x,y","say ""hi"""\r\n"line\nbreak",3',
    );
  });

  it("neutralises spreadsheet formulas", () => {
    expect(toCsv(["a"], [["=SUM(A1)"]])).toBe("a\r\n'=SUM(A1)");
  });
});

describe("coursesToCsv", () => {
  it("exports the given rows with headings and status labels", () => {
    const lines = coursesToCsv([courses[1]]).split("\r\n");
    expect(lines[0]).toBe("Course code,Course name,Lecturer,Enrolled,Attendance (%),Status");
    expect(lines[1]).toBe('CS6101,"Advanced ""Databases""",N. Perera,12,70,Correction needed');
    expect(lines).toHaveLength(2);
  });
});
