import { describe, expect, it } from "vitest";
import {
  classroomStatusDisplay,
  courseStatusDisplay,
  finalStatusDisplay,
  geofenceResultDisplay,
  reviewCaseStatusDisplay,
  riskLevelDisplay,
  sessionStatusDisplay,
  syncStatusDisplay,
  verificationOutcomeDisplay,
  verificationOutcomeLabel,
} from "@/lib/status";

describe("sessionStatusDisplay", () => {
  it("maps in_progress to a success badge", () => {
    expect(sessionStatusDisplay("in_progress")).toEqual({ label: "In progress", tone: "success" });
  });

  it("maps scheduled to an info badge", () => {
    expect(sessionStatusDisplay("scheduled")).toEqual({ label: "Upcoming", tone: "info" });
  });

  it("maps closed to a neutral badge", () => {
    expect(sessionStatusDisplay("closed")).toEqual({ label: "Closed", tone: "neutral" });
  });
});

describe("verificationOutcomeDisplay", () => {
  it("returns a badge for present/failed/late/participated", () => {
    expect(verificationOutcomeDisplay("present")?.tone).toBe("success");
    expect(verificationOutcomeDisplay("failed")?.tone).toBe("danger");
    expect(verificationOutcomeDisplay("late")?.tone).toBe("warning");
    expect(verificationOutcomeDisplay("participated")?.tone).toBe("purple");
  });

  it("returns null for outcomes that render as plain text instead of a badge", () => {
    expect(verificationOutcomeDisplay("not_launched")).toBeNull();
    expect(verificationOutcomeDisplay("not_required")).toBeNull();
    expect(verificationOutcomeDisplay("not_submitted")).toBeNull();
    expect(verificationOutcomeDisplay("not_participated")).toBeNull();
  });
});

describe("verificationOutcomeLabel", () => {
  it("humanises snake_case outcomes not covered by a badge", () => {
    expect(verificationOutcomeLabel("not_launched")).toBe("Not launched");
    expect(verificationOutcomeLabel("not_required")).toBe("Not required");
    expect(verificationOutcomeLabel("not_submitted")).toBe("Not submitted");
    expect(verificationOutcomeLabel("not_participated")).toBe("Not participated");
  });
});

describe("finalStatusDisplay", () => {
  it("maps every final status to the right tone", () => {
    expect(finalStatusDisplay("present").tone).toBe("success");
    expect(finalStatusDisplay("late").tone).toBe("warning");
    expect(finalStatusDisplay("absent").tone).toBe("danger");
    expect(finalStatusDisplay("pending_review").tone).toBe("warning");
  });
});

describe("courseStatusDisplay", () => {
  it("flags correction_needed as a warning, active as success", () => {
    expect(courseStatusDisplay("active")).toEqual({ label: "Active", tone: "success" });
    expect(courseStatusDisplay("correction_needed")).toEqual({ label: "Correction needed", tone: "warning" });
  });
});

describe("reviewCaseStatusDisplay", () => {
  it("maps pending/information", () => {
    expect(reviewCaseStatusDisplay("pending").tone).toBe("warning");
    expect(reviewCaseStatusDisplay("information").tone).toBe("info");
  });
});

describe("geofenceResultDisplay", () => {
  it("maps within_radius/boundary/outside_radius", () => {
    expect(geofenceResultDisplay("within_radius").tone).toBe("success");
    expect(geofenceResultDisplay("boundary").tone).toBe("warning");
    expect(geofenceResultDisplay("outside_radius").tone).toBe("danger");
  });
});

describe("riskLevelDisplay", () => {
  it("maps high/medium/low", () => {
    expect(riskLevelDisplay("high").tone).toBe("danger");
    expect(riskLevelDisplay("medium").tone).toBe("warning");
    expect(riskLevelDisplay("low").tone).toBe("success");
  });
});

describe("classroomStatusDisplay", () => {
  it("maps active/needs_review", () => {
    expect(classroomStatusDisplay("active").tone).toBe("success");
    expect(classroomStatusDisplay("needs_review").tone).toBe("warning");
  });
});

describe("syncStatusDisplay", () => {
  it("maps current/review", () => {
    expect(syncStatusDisplay("current").tone).toBe("success");
    expect(syncStatusDisplay("review").tone).toBe("warning");
  });
});
