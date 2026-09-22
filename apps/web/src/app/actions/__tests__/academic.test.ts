import { beforeEach, describe, expect, it, vi } from "vitest";
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
} from "@/lib/api/admin";
import { CoreBackendError } from "@/lib/api/coreBackend";
import {
  addEnrolment,
  removeEnrolment,
  removeTimetableEntry,
  saveCourse,
  saveOffering,
  saveTimetableEntry,
} from "@/app/actions/academic";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("server-only", () => ({}));
vi.mock("@/lib/api/coreBackend", () => ({
  CoreBackendError: class CoreBackendError extends Error {
    constructor(message: string, public status: number, public path: string) {
      super(message);
    }
  },
}));
vi.mock("@/lib/api/admin", () => ({
  createCourse: vi.fn(),
  updateCourse: vi.fn(),
  createOffering: vi.fn(),
  updateOffering: vi.fn(),
  enrolStudent: vi.fn(),
  dropStudent: vi.fn(),
  createTimetableEntry: vi.fn(),
  updateTimetableEntry: vi.fn(),
  deactivateTimetableEntry: vi.fn(),
}));

const course = {
  courseCode: "CS3203",
  courseName: "Software Engineering Project",
  departmentId: "department-1",
  credits: 3,
  status: "active" as const,
};

const offering = {
  courseId: "course-1",
  semesterId: "semester-1",
  lecturerId: "lecturer-1",
  batchYear: 2023,
  courseType: "lecture",
  attendanceThresholdPercent: 80,
  status: "active" as const,
};

const timetable = {
  courseOfferingId: "offering-1",
  classroomId: "classroom-1",
  dayOfWeek: 1,
  startTime: "09:00",
  endTime: "10:00",
  courseType: "lecture",
  validFrom: "2026-01-01",
  validUntil: null,
  status: "active" as const,
};

beforeEach(() => vi.clearAllMocks());

describe("academic management actions", () => {
  it("creates and updates courses", async () => {
    vi.mocked(createCourse).mockResolvedValue({} as never);
    vi.mocked(updateCourse).mockResolvedValue({} as never);

    expect(await saveCourse(null, course)).toEqual({ ok: true });
    expect(createCourse).toHaveBeenCalledWith(course);
    expect(await saveCourse("course-1", course)).toEqual({ ok: true });
    expect(updateCourse).toHaveBeenCalledWith("course-1", course);
    expect(revalidatePath).toHaveBeenCalledWith("/admin/academic");
  });

  it("preserves a clean duplicate message", async () => {
    vi.mocked(createCourse).mockRejectedValue(
      new CoreBackendError("A course with this code already exists.", 409, "/courses"),
    );

    expect(await saveCourse(null, course)).toEqual({
      ok: false,
      message: "A course with this code already exists.",
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("creates and updates offerings", async () => {
    vi.mocked(createOffering).mockResolvedValue({} as never);
    vi.mocked(updateOffering).mockResolvedValue({} as never);

    expect(await saveOffering(null, offering)).toEqual({ ok: true });
    expect(await saveOffering("offering-1", offering)).toEqual({ ok: true });
    expect(createOffering).toHaveBeenCalledWith(offering);
    expect(updateOffering).toHaveBeenCalledWith("offering-1", offering);
  });

  it("enrols and drops without deleting through the action contract", async () => {
    vi.mocked(enrolStudent).mockResolvedValue({} as never);
    vi.mocked(dropStudent).mockResolvedValue({} as never);

    expect(await addEnrolment("offering-1", "student-1")).toEqual({ ok: true });
    expect(await removeEnrolment("offering-1", "student-1")).toEqual({ ok: true });
    expect(dropStudent).toHaveBeenCalledWith("offering-1", "student-1");
  });

  it("creates, updates and deactivates timetable entries", async () => {
    vi.mocked(createTimetableEntry).mockResolvedValue({} as never);
    vi.mocked(updateTimetableEntry).mockResolvedValue({} as never);
    vi.mocked(deactivateTimetableEntry).mockResolvedValue({} as never);

    expect(await saveTimetableEntry(null, timetable)).toEqual({ ok: true });
    expect(await saveTimetableEntry("entry-1", timetable)).toEqual({ ok: true });
    expect(await removeTimetableEntry("entry-1")).toEqual({ ok: true });
    expect(deactivateTimetableEntry).toHaveBeenCalledWith("entry-1");
  });
});
