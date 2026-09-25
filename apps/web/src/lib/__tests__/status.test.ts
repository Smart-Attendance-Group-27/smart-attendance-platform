import { describe, expect, it } from "vitest";
import {
  classroomStatusDisplay,
  courseStatusDisplay,
  weeklyDeltaNote,
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

  it("maps cancelled to a danger badge", () => {
    expect(sessionStatusDisplay("cancelled")).toEqual({ label: "Cancelled", tone: "danger" });
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
    expect(verificationOutcomeDisplay("not_required")).toBeNull();
    expect(verificationOutcomeDisplay("not_submitted")).toBeNull();
    expect(verificationOutcomeDisplay("not_participated")).toBeNull();
  });
});

describe("verificationOutcomeLabel", () => {
  it("humanises snake_case outcomes not covered by a badge", () => {
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
  it("shows active as success and never invents a correction state", () => {
    expect(courseStatusDisplay("active")).toEqual({ label: "Active", tone: "success" });
    expect(courseStatusDisplay("inactive")).toEqual({ label: "Inactive", tone: "neutral" });
    expect(courseStatusDisplay("completed")).toEqual({ label: "Completed", tone: "neutral" });
    expect(courseStatusDisplay("on_hold")).toEqual({ label: "On hold", tone: "neutral" });
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
    expect(geofenceResultDisplay("not_recorded")).toEqual({ label: "Not recorded", tone: "neutral" });
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

describe("weeklyDeltaNote", () => {
  it("words the change by its direction and never invents a comparison", () => {
    expect(weeklyDeltaNote(4.6)).toEqual({ note: "Up 4.6% from last week", tone: "good" });
    expect(weeklyDeltaNote(-3.2)).toEqual({ note: "Down 3.2% from last week", tone: "warn" });
    expect(weeklyDeltaNote(0)).toEqual({ note: "No change from last week", tone: "neutral" });
    expect(weeklyDeltaNote(null)).toEqual({ note: "No previous week to compare", tone: "neutral" });
  });
});
