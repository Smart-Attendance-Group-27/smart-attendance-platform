import { describe, expect, it, vi } from "vitest";
import { auditActionLabel, auditDetailLines, auditEntityLabel } from "@/lib/auditDetails";

vi.mock("server-only", () => ({}));

const base = {
  entityType: "attendance_session",
  entityId: "40000000-0000-0000-0000-000000000001",
  newValues: null,
  metadata: null,
  sessionCourseCode: "CS3053",
  sessionScheduledStartAt: null,
};

describe("audit details", () => {
  it("describes a session geofence waiver", () => {
    const entry = {
      ...base,
      action: "session.verification_override",
      metadata: {
        verificationFactor: "geofence", scope: "session", previousPolicy: "required",
        newPolicy: "waived", reasonCode: "GPS_UNAVAILABLE", reasonText: null,
        affectedStudentCount: 238,
      },
    };

    expect(auditActionLabel(entry.action)).toBe("Session verification override");
    expect(auditDetailLines(entry)).toEqual([
      "Factor: Geofence",
      "Change: REQUIRED -> WAIVED",
      "Scope: Entire session",
      "Reason: GPS unavailable",
      "Affected students: 238",
    ]);
  });

  it("describes an automatic close", () => {
    const lines = auditDetailLines({
      ...base,
      action: "session.auto_close",
      newValues: { graceMinutes: 15, reason: "Scheduled end plus grace period exceeded" },
    });

    expect(lines).toContain("Grace period: 15 min");
    expect(lines).toContain("Reason: Scheduled end plus grace period exceeded");
  });

  it("names a session by its course", () => {
    expect(auditEntityLabel({ ...base, action: "session.close" })).toBe("Session: CS3053 / 40000000");
  });

  it("leaves other actions without details", () => {
    expect(auditDetailLines({ ...base, action: "manual_review.decide" })).toEqual([]);
  });
});
