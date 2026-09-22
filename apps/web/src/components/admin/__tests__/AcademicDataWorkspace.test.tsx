import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { saveCourse } from "@/app/actions/academic";
import { AcademicDataWorkspace } from "@/components/admin/AcademicDataWorkspace";
import type { AcademicData, AcademicReferenceData } from "@/types/admin";

vi.mock("@/app/actions/academic", () => ({
  saveCourse: vi.fn(),
  saveOffering: vi.fn(),
  saveTimetableEntry: vi.fn(),
  addEnrolment: vi.fn(),
  removeEnrolment: vi.fn(),
  removeTimetableEntry: vi.fn(),
}));

vi.mock("@/components/ui/Dialog", () => ({
  Dialog: ({ open, title, children }: { open: boolean; title: string; children: React.ReactNode }) =>
    open ? <section aria-label={title}>{children}</section> : null,
  ConfirmationDialog: () => null,
}));

const data: AcademicData = {
  sourceConnectionStatus: "not_configured",
  courses: [{
    courseId: "course-1",
    courseCode: "CS3203",
    courseName: "Software Engineering Project",
    departmentId: "department-1",
    department: "Computer Science",
    credits: 3,
    status: "active",
  }],
  offerings: [],
  timetable: [],
  enrolments: [],
};

const references: AcademicReferenceData = {
  departments: [{ id: "department-1", label: "Computer Science" }],
  semesters: [{ id: "semester-1", label: "Semester 1 (2026)" }],
  lecturers: [{ id: "lecturer-1", label: "N. Perera" }],
  students: [{ id: "student-1", label: "230701A - Amal Perera" }],
  classrooms: [{ id: "classroom-1", label: "LH-02" }],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(saveCourse).mockResolvedValue({ ok: true });
});

describe("AcademicDataWorkspace", () => {
  it("renders the aggregate and submits a new course", async () => {
    render(<AcademicDataWorkspace data={data} references={references} />);

    expect(screen.getByText("CS3203")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add course" }));
    fireEvent.change(screen.getByLabelText("Course code"), { target: { value: "CS4201" } });
    fireEvent.change(screen.getByLabelText("Course name"), { target: { value: "Distributed Systems" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(saveCourse).toHaveBeenCalledWith(null, {
      courseCode: "CS4201",
      courseName: "Distributed Systems",
      departmentId: "department-1",
      credits: 3,
      status: "active",
    }));
  });
});
