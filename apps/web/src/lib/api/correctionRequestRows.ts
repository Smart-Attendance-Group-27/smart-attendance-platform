import "server-only";
import { formatDateTimeLabel, formatDayOfWeek, formatTimeRange } from "@/lib/api/format";
import { correctionCategoryLabel, type CorrectionRequestRow, type CorrectionRequestType } from "@/lib/correctionRequests";

type ApiCorrectionRequestLike = {
  id: string;
  requestType: CorrectionRequestType;
  category: string;
  requesterName?: string;
  courseCode: string | null;
  courseName: string | null;
  timetableDayOfWeek: number | null;
  timetableStartTime: string | null;
  timetableEndTime: string | null;
  timetableClassroomCode: string | null;
  description: string;
  status: string;
  reviewNote: string | null;
  createdAt: string;
  reviewedAt: string | null;
};

export function toCorrectionRequestRow(item: ApiCorrectionRequestLike): CorrectionRequestRow {
  const hasTimetableEntry = item.timetableDayOfWeek !== null;
  return {
    id: item.id,
    requestType: item.requestType,
    typeLabel: item.requestType === "timetable" ? "Timetable" : "Course data",
    categoryLabel: correctionCategoryLabel(item.category),
    courseLabel: [item.courseCode, item.courseName].filter(Boolean).join(" · ") || "—",
    targetLabel: hasTimetableEntry
      ? `${formatDayOfWeek(item.timetableDayOfWeek as number)} ${formatTimeRange(item.timetableStartTime, item.timetableEndTime)} · ${item.timetableClassroomCode ?? "No room"}`
      : "—",
    requesterName: item.requesterName ?? "",
    description: item.description,
    status: item.status,
    reviewNote: item.reviewNote,
    createdLabel: formatDateTimeLabel(item.createdAt),
    reviewedLabel: item.reviewedAt ? formatDateTimeLabel(item.reviewedAt) : null,
  };
}
