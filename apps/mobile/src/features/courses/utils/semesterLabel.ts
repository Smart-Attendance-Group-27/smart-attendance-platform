// The semester shared by every listed course, or null when the list is empty or
// spans more than one semester (each card still shows its own semester).
export function getCommonSemester(courses: { semester: string }[]): string | null {
  const semesters = new Set(courses.map((course) => course.semester.trim()).filter(Boolean));
  return semesters.size === 1 ? [...semesters][0] : null;
}
