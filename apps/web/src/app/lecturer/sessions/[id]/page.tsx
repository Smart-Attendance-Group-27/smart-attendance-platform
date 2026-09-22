import { notFound } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LinkButton } from "@/components/ui/LinkButton";
import { SessionLifecycleControls } from "@/components/lecturer/SessionLifecycleControls";
import { SessionLiveRefresh } from "@/components/lecturer/SessionLiveRefresh";
import { ManualAttendanceDialog } from "@/components/lecturer/ManualAttendanceDialog";
import { getSessionDetail } from "@/services/lecturerService";
import { formatDateTimeLabel } from "@/lib/api/format";
import { initialCheckInDisplay, liveFinalStatusDisplay, qrProgressLabel, sessionStatusDisplay } from "@/lib/status";
import type { LiveSessionStudentRow } from "@/types/lecturer";
import { isWebMockMode } from "@/lib/api/mode";

export default async function SessionMonitorPage(props: PageProps<"/lecturer/sessions/[id]">) {
  const { id } = await props.params;
  const session = await getSessionDetail(id);
  if (!session) notFound();

  const status = sessionStatusDisplay(session.status);
  const isActive = session.status === "in_progress";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Live session monitor"
        description={`${session.courseCode} · ${session.courseName} · ${session.room}`}
        actions={isWebMockMode()
          ? <span className="text-xs text-[var(--muted)]">Mock preview · actions unavailable</span>
          : <SessionLifecycleControls sessionId={session.sessionId} status={session.status} />}
      />

      {session.status === "cancelled" ? (
        <Notice variant="warning" title="Session cancelled.">
          {session.cancellationReason ?? "No reason was recorded."}
        </Notice>
      ) : null}

      <Card flush>
        <div className="grid grid-cols-1 border-b border-[var(--line)] sm:grid-cols-2 lg:grid-cols-[1.3fr_repeat(4,minmax(120px,1fr))]">
          <div className="border-b border-[var(--line-soft)] p-4 lg:border-b-0 lg:border-r">
            <p className="text-lg font-semibold text-[#2d3d49]">{session.courseCode} {session.courseName}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{session.startedAtLabel}</p>
            <div className="mt-2"><StatusBadge tone={status.tone}>{status.label}</StatusBadge></div>
          </div>
          {[
            { label: "Check-in window", value: session.checkInWindow },
            { label: "Late threshold", value: session.lateThreshold },
            { label: "Room", value: session.room },
            { label: "Lecturer", value: session.lecturerName },
          ].map((meta) => (
            <div key={meta.label} className="border-b border-[var(--line-soft)] p-4 last:border-r-0 lg:border-b-0 lg:border-r">
              <p className="text-[10px] uppercase tracking-wide text-[var(--muted)]">{meta.label}</p>
              <p className="mt-1.5 text-xs font-semibold">{meta.value}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] bg-[#fafbfc] p-2.5">
          {session.requiresQr ? (
            <LinkButton href={`/lecturer/sessions/${session.sessionId}/qr`}>Manage QR batches</LinkButton>
          ) : <span className="text-xs text-[var(--muted)]">QR is disabled for this session.</span>}
          {isActive ? <SessionLiveRefresh /> : null}
        </div>

        <SummaryStrip items={[
          { label: "Checked in", value: session.summary.checkedInCount, note: "On time", noteTone: "good" },
          { label: "Checked in late", value: session.summary.lateCheckedInCount, noteTone: "warn" },
          { label: "Not checked in", value: session.summary.notCheckedInCount },
          { label: "Failed verification", value: session.summary.failedVerificationCount, noteTone: "warn" },
        ]} />
        <SummaryStrip items={[
          { label: "Final present", value: session.summary.presentCount },
          { label: "Final late", value: session.summary.lateCount },
          { label: "Final absent", value: session.summary.absentCount },
          { label: "Manual records", value: session.summary.manualCount },
          { label: "Pending review", value: session.summary.pendingReviewCount },
        ]} />

        <DataTable<LiveSessionStudentRow>
          emptyTitle="No students on the roster"
          emptyDescription="Enrolled students will appear here."
          columns={[
            { key: "student", header: "Student", render: (row) =>
              <CellPrimary primary={row.fullName} secondary={row.studentIndex} /> },
            { key: "initial", header: "Initial check-in", render: (row) => {
              const display = initialCheckInDisplay(row);
              return <div><StatusBadge tone={display.tone}>{display.label}</StatusBadge>
                {row.failureReason ? <span className="mt-1 block text-[10px] text-[var(--muted)]">
                  {row.failureReason.replaceAll("_", " ")}</span> : null}</div>;
            } },
            { key: "time", header: "Checked in at", render: (row) => formatDateTimeLabel(row.checkedInAt) },
            { key: "face", header: "Face", render: (row) =>
              session.requiresFaceVerification ? (row.faceStatus ?? "—") : "Not required" },
            { key: "qr", header: "QR passed / required", render: (row) =>
              session.requiresQr ? qrProgressLabel(row) : "Not required" },
            { key: "final", header: "Final result", render: (row) => {
              const display = liveFinalStatusDisplay(row, session.status);
              return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
            } },
            { key: "source", header: "Source", render: (row) => row.recordSource === "manual"
              ? <span><StatusBadge tone="purple">Manual</StatusBadge>
                {row.manualReason ? <span className="mt-1 block text-[10px] text-[var(--muted)]">{row.manualReason}</span> : null}
              </span>
              : row.recordSource === "automatic" ? "Automatic" : "—" },
            { key: "action", header: "Action", align: "right", render: (row) => (
              <div className="flex justify-end gap-2">
                {row.reviewStatus === "pending" ? <LinkButton href="/lecturer/review">Review</LinkButton> : null}
                {!isWebMockMode() && (session.status === "in_progress" || session.status === "closed")
                  ? <ManualAttendanceDialog sessionId={session.sessionId} student={row} /> : null}
              </div>
            ) },
          ]}
          rows={session.students}
          getRowKey={(row) => row.studentId}
        />
      </Card>
    </div>
  );
}
