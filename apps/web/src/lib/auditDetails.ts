import { formatDateTimeLabel } from "@/lib/api/format";
import { geofenceWaiverReasonLabel } from "@/lib/geofenceWaiver";

type AuditValues = Record<string, unknown> | null;

export type AuditDetailInput = {
  action: string;
  entityType: string;
  entityId: string | null;
  newValues: AuditValues;
  metadata: AuditValues;
  sessionCourseCode: string | null;
  sessionScheduledStartAt: string | null;
};

const ACTION_LABELS: Record<string, string> = {
  "session.verification_override": "Session verification override",
  "session.auto_close": "Session automatically closed",
  "session.close": "Session closed",
};

const FACTOR_LABELS: Record<string, string> = {
  geofence: "Geofence",
  face_verification: "Face verification",
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function count(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function auditActionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

export function auditEntityLabel(entry: AuditDetailInput): string {
  if (entry.entityType === "attendance_session" && entry.sessionCourseCode) {
    const when = entry.sessionScheduledStartAt
      ? formatDateTimeLabel(entry.sessionScheduledStartAt)
      : entry.entityId?.slice(0, 8) ?? "";
    return `Session: ${entry.sessionCourseCode} / ${when}`;
  }
  return entry.entityId ? `${entry.entityType} · ${entry.entityId.slice(0, 8)}` : entry.entityType;
}

// Readable lines for the actions that carry structured audit values.
export function auditDetailLines(entry: AuditDetailInput): string[] {
  const metadata = entry.metadata ?? {};
  const values = entry.newValues ?? {};

  if (entry.action === "session.verification_override") {
    const factor = text(metadata.verificationFactor);
    const previous = text(metadata.previousPolicy);
    const next = text(metadata.newPolicy);
    const reasonCode = text(metadata.reasonCode);
    const reasonText = text(metadata.reasonText);
    const affected = count(metadata.affectedStudentCount);
    const lines = [
      `Factor: ${factor ? FACTOR_LABELS[factor] ?? factor : "Unknown"}`,
      `Change: ${(previous ?? "?").toUpperCase()} -> ${(next ?? "?").toUpperCase()}`,
      `Scope: ${metadata.scope === "session" ? "Entire session" : text(metadata.scope) ?? "Unknown"}`,
    ];
    if (reasonCode) {
      lines.push(`Reason: ${geofenceWaiverReasonLabel(reasonCode)}${reasonText ? ` (${reasonText})` : ""}`);
    }
    if (affected !== null) lines.push(`Affected students: ${affected}`);
    return lines;
  }

  if (entry.action === "session.auto_close") {
    const lines: string[] = [];
    const scheduledEnd = text(values.scheduledEndAt);
    const closedAt = text(values.closedAt);
    const grace = count(values.graceMinutes);
    if (scheduledEnd) lines.push(`Scheduled end: ${formatDateTimeLabel(scheduledEnd)}`);
    if (closedAt) lines.push(`Closed at: ${formatDateTimeLabel(closedAt)}`);
    if (grace !== null) lines.push(`Grace period: ${grace} min`);
    const reason = text(values.reason);
    if (reason) lines.push(`Reason: ${reason}`);
    return lines;
  }

  return [];
}
