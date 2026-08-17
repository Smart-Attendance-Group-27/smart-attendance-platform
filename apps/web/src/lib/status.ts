import { StatusTone } from "@/components/ui/StatusBadge";

type StatusDisplay = { label: string; tone: StatusTone };

export function sessionStatusDisplay(status: "scheduled" | "in_progress" | "closed" | "cancelled"): StatusDisplay {
  switch (status) {
    case "in_progress":
      return { label: "In progress", tone: "success" };
    case "scheduled":
      return { label: "Upcoming", tone: "info" };
    case "closed":
      return { label: "Closed", tone: "neutral" };
    case "cancelled":
      return { label: "Cancelled", tone: "danger" };
  }
}

export function verificationOutcomeDisplay(
  outcome:
    | "present"
    | "failed"
    | "late"
    | "not_required"
    | "not_submitted"
    | "not_participated"
    | "participated",
): StatusDisplay | null {
  switch (outcome) {
    case "present":
      return { label: "Present", tone: "success" };
    case "failed":
      return { label: "Failed", tone: "danger" };
    case "late":
      return { label: "Late", tone: "warning" };
    case "participated":
      return { label: "Participated", tone: "purple" };
    case "not_required":
      return null;
    case "not_submitted":
      return null;
    case "not_participated":
      return null;
  }
}

export function verificationOutcomeLabel(
  outcome:
    | "present"
    | "failed"
    | "late"
    | "not_required"
    | "not_submitted"
    | "not_participated"
    | "participated",
): string {
  switch (outcome) {
    case "not_required":
      return "Not required";
    case "not_submitted":
      return "Not submitted";
    case "not_participated":
      return "Not participated";
    default:
      return outcome;
  }
}

export function finalStatusDisplay(status: "present" | "late" | "absent" | "pending_review"): StatusDisplay {
  switch (status) {
    case "present":
      return { label: "Present", tone: "success" };
    case "late":
      return { label: "Late", tone: "warning" };
    case "absent":
      return { label: "Absent", tone: "danger" };
    case "pending_review":
      return { label: "Pending review", tone: "warning" };
  }
}

export function courseStatusDisplay(status: "active" | "correction_needed"): StatusDisplay {
  return status === "active"
    ? { label: "Active", tone: "success" }
    : { label: "Correction needed", tone: "warning" };
}

export function reviewCaseStatusDisplay(status: "pending" | "information"): StatusDisplay {
  return status === "pending" ? { label: "Pending", tone: "warning" } : { label: "Information", tone: "info" };
}

export function geofenceResultDisplay(result: "within_radius" | "boundary" | "outside_radius"): StatusDisplay {
  switch (result) {
    case "within_radius":
      return { label: "Within radius", tone: "success" };
    case "boundary":
      return { label: "Boundary", tone: "warning" };
    case "outside_radius":
      return { label: "Outside radius", tone: "danger" };
  }
}

export function classroomStatusDisplay(status: "active" | "needs_review"): StatusDisplay {
  return status === "active" ? { label: "Active", tone: "success" } : { label: "Needs review", tone: "warning" };
}

export function syncStatusDisplay(status: "current" | "review"): StatusDisplay {
  return status === "current" ? { label: "Current", tone: "success" } : { label: "Review", tone: "warning" };
}

export function riskLevelDisplay(risk: "high" | "medium" | "low"): StatusDisplay {
  switch (risk) {
    case "high":
      return { label: "High", tone: "danger" };
    case "medium":
      return { label: "Medium", tone: "warning" };
    case "low":
      return { label: "Low", tone: "success" };
  }
}

export function accountStatusDisplay(status: "active" | "suspended" | "locked"): StatusDisplay {
  switch (status) {
    case "active":
      return { label: "Active", tone: "success" };
    case "suspended":
      return { label: "Suspended", tone: "warning" };
    case "locked":
      return { label: "Locked", tone: "danger" };
  }
}

export function profileStatusDisplay(status: "active" | "inactive"): StatusDisplay {
  return status === "active" ? { label: "Active", tone: "success" } : { label: "Inactive", tone: "neutral" };
}

export function academicRecordStatusDisplay(status: "active" | "inactive"): StatusDisplay {
  return status === "active" ? { label: "Active", tone: "success" } : { label: "Inactive", tone: "neutral" };
}

export function embeddingGenerationStatusDisplay(
  status: "pending" | "generated" | "failed" | "revoked",
): StatusDisplay {
  switch (status) {
    case "pending":
      return { label: "Pending", tone: "info" };
    case "generated":
      return { label: "Generated", tone: "success" };
    case "failed":
      return { label: "Failed", tone: "danger" };
    case "revoked":
      return { label: "Revoked", tone: "neutral" };
  }
}

export function readinessStatusDisplay(status: "not_checked" | "passed" | "failed" | "expired"): StatusDisplay {
  switch (status) {
    case "not_checked":
      return { label: "Not checked", tone: "neutral" };
    case "passed":
      return { label: "Passed", tone: "success" };
    case "failed":
      return { label: "Failed", tone: "danger" };
    case "expired":
      return { label: "Expired", tone: "warning" };
  }
}

export function auditOutcomeDisplay(outcome: "success" | "failure"): StatusDisplay {
  return outcome === "success" ? { label: "Success", tone: "success" } : { label: "Failure", tone: "danger" };
}

export function enrolmentStatusDisplay(status: "enrolled" | "dropped"): StatusDisplay {
  return status === "enrolled" ? { label: "Enrolled", tone: "success" } : { label: "Dropped", tone: "neutral" };
}
