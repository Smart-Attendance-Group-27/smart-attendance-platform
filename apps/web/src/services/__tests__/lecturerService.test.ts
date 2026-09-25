import { describe, expect, it, vi } from "vitest";
import { getReviewCases, getSessionDetail } from "@/services/lecturerService";
import { CoreBackendError } from "@/lib/api/coreBackend";
import type { ApiLecturerSession, ApiManualReviewQueueItem, ApiSessionStudent } from "@/lib/api/lecturer";

// lecturerService.ts is `import "server-only"` — outside Next's own build,
// that import throws by design. Vitest runs this file directly, not through
// Next's bundler, so the guard has nothing to enforce here and is a no-op.
vi.mock("server-only", () => ({}));

vi.mock("@/lib/auth/dal", () => ({
  getCurrentUser: vi.fn().mockResolvedValue({ name: "Nadeesha Perera", role: "lecturer" }),
}));
vi.mock("@/lib/api/mode", () => ({
  isWebMockMode: vi.fn().mockReturnValue(false),
}));

const { getLecturerSessionDetail, getLecturerSessionStudents, getManualReviewQueue } = vi.hoisted(() => ({
  getLecturerSessionDetail: vi.fn(),
  getLecturerSessionStudents: vi.fn(),
  getManualReviewQueue: vi.fn(),
}));
vi.mock("@/lib/api/lecturer", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/lecturer")>();
  return { ...actual, getLecturerSessionDetail, getLecturerSessionStudents, getManualReviewQueue };
});

const baseSession: ApiLecturerSession = {
  id: "session-1",
  courseOfferingId: "offering-1",
  courseCode: "CS3203",
  courseName: "Software Engineering Project",
  classroomCode: "LT-301",
  status: "active",
  scheduledStartAt: "2026-09-22T09:00:00.000Z",
  scheduledEndAt: "2026-09-22T10:00:00.000Z",
  checkInOpensAt: "2026-09-22T09:00:00.000Z",
  checkInClosesAt: "2026-09-22T09:15:00.000Z",
  lateAfterAt: "2026-09-22T09:10:00.000Z",
  activatedAt: "2026-09-22T09:00:00.000Z",
  closedAt: null,
  cancelledAt: null,
  cancellationReason: null,
  requiresFaceVerification: true,
  requiresGeofence: true,
  requiresQr: false,
  enrolledCount: 5,
  presentCount: 0,
  lateCount: 0,
  pendingReviewCount: 0,
  checkedInCount: 0,
  lateCheckedInCount: 0,
  notCheckedInCount: 5,
  failedVerificationCount: 0,
  absentCount: 0,
  manualCount: 0,
};

const noStudents: ApiSessionStudent[] = [];

describe("getSessionDetail", () => {
  it("carries no cancellation reason for an active session", async () => {
    getLecturerSessionDetail.mockResolvedValue(baseSession);
    getLecturerSessionStudents.mockResolvedValue(noStudents);

    const detail = await getSessionDetail("session-1");

    expect(detail?.status).toBe("in_progress");
    expect(detail?.cancellationReason).toBeNull();
  });

  it("carries the cancellation reason through for a cancelled session", async () => {
    getLecturerSessionDetail.mockResolvedValue({
      ...baseSession,
      status: "cancelled",
      cancelledAt: "2026-09-22T09:05:00.000Z",
      cancellationReason: "The lecturer is unwell.",
    });
    getLecturerSessionStudents.mockResolvedValue(noStudents);

    const detail = await getSessionDetail("session-1");

    expect(detail?.status).toBe("cancelled");
    expect(detail?.cancellationReason).toBe("The lecturer is unwell.");
  });

  it("returns null when the backend says the session does not exist", async () => {
    getLecturerSessionDetail.mockRejectedValue(new CoreBackendError("not found", 404, "/x"));

    expect(await getSessionDetail("missing-session")).toBeNull();
  });

  it.each([500, 401, 403])("does not report a %i failure as not found", async (status) => {
    getLecturerSessionDetail.mockRejectedValue(new CoreBackendError("failed", status, "/x"));

    await expect(getSessionDetail("session-1")).rejects.toBeInstanceOf(CoreBackendError);
  });

  it("does not report a network failure as not found", async () => {
    getLecturerSessionDetail.mockRejectedValue(new TypeError("fetch failed"));

    await expect(getSessionDetail("session-1")).rejects.toThrow("fetch failed");
  });
});

const baseReviewItem: ApiManualReviewQueueItem = {
  verificationAttemptId: "attempt-1",
  sessionId: "session-1",
  courseCode: "CS3203",
  courseName: "Software Engineering Project",
  classroomCode: "LT-301",
  scheduledStartAt: "2026-09-22T09:00:00.000Z",
  studentId: "student-1",
  registrationNumber: "230701A",
  fullName: "Test Student",
  failureReason: null,
  startedAt: "2026-09-22T09:05:00.000Z",
  completedAt: null,
  geofenceStatus: null,
  geofenceFailureReason: null,
  faceStatus: null,
  faceSimilarityScore: null,
  faceSimilarityThreshold: null,
  faceLivenessPassed: null,
  qrStatus: null,
  reviewStatus: "pending",
  decisionReason: null,
  reviewedAt: null,
};

describe("getReviewCases", () => {
  it("does not invent a duplicate submission, geofence pass or face score for unknown data", async () => {
    getManualReviewQueue.mockResolvedValue([{ ...baseReviewItem, failureReason: "SOMETHING_ELSE" }]);

    const [review] = await getReviewCases();

    expect(review.issueType).toBe("other_verification_issue");
    expect(review.issueLabel).toBe("Something Else");
    expect(review.geofenceResult).toBe("not_recorded");
    expect(review.faceScorePercent).toBeNull();
    expect(review.livenessPassed).toBeNull();
    expect(review.geofenceDistanceMeters).toBeNull();
    expect(review.faceThresholdPercent).toBeNull();
  });

  it("carries the configured face threshold through as a percentage", async () => {
    getManualReviewQueue.mockResolvedValue([
      { ...baseReviewItem, faceStatus: "failed", faceSimilarityScore: 0.72, faceSimilarityThreshold: 0.725 },
    ]);

    const [review] = await getReviewCases();

    expect(review.faceScorePercent).toBe(72);
    expect(review.faceThresholdPercent).toBe(72.5);
  });

  it("reports a passed geofence and a recorded face score when the backend has them", async () => {
    getManualReviewQueue.mockResolvedValue([
      { ...baseReviewItem, geofenceStatus: "passed", faceStatus: "failed", faceSimilarityScore: 0.48, faceLivenessPassed: true },
    ]);

    const [review] = await getReviewCases();

    expect(review.issueType).toBe("low_confidence_face_match");
    expect(review.geofenceResult).toBe("within_radius");
    expect(review.faceScorePercent).toBe(48);
    expect(review.livenessPassed).toBe(true);
  });
});
