import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LinkButton } from "@/components/ui/LinkButton";
import { CreateSessionButton } from "@/components/lecturer/CreateSessionButton";
import { getSessionCreationOptions, getSessionList } from "@/services/lecturerService";
import { sessionStatusDisplay } from "@/lib/status";
import { TodayLecture } from "@/types/lecturer";
import { isWebMockMode } from "@/lib/api/mode";

export default async function LecturerSessionsPage() {
  const [sessions, timetableOptions] = await Promise.all([
    getSessionList(),
    getSessionCreationOptions(),
  ]);

  return (
    <div>
      <PageHeader
        title="Attendance sessions"
        description="View and monitor your attendance sessions."
        actions={isWebMockMode()
          ? <span className="text-xs text-[var(--muted)]">Mock preview · creation unavailable</span>
          : <CreateSessionButton timetableOptions={timetableOptions} />}
      />

      <Card flush>
        <DataTable<TodayLecture>
          emptyTitle="No attendance sessions yet"
          emptyDescription="Sessions from your assigned courses will appear here."
          columns={[
            {
              key: "course",
              header: "Course",
              render: (row) => <CellPrimary primary={row.courseCode} secondary={row.courseName} />,
            },
            {
              key: "time",
              header: "Time and room",
              render: (row) => (
                <>
                  {row.timeRange}
                  <span className="mt-0.5 block text-[10px] text-[var(--muted)]">{row.room}</span>
                </>
              ),
            },
            { key: "checkin", header: "Check-in", render: (row) => row.checkInWindow },
            {
              key: "attendance",
              header: "Initial check-in",
              render: (row) => `${(row.checkedInCount ?? 0) + (row.lateCheckedInCount ?? 0)} / ${row.enrolledCount}`,
            },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = sessionStatusDisplay(row.status);
                return <div>
                  <StatusBadge tone={display.tone}>{display.label}</StatusBadge>
                  {row.status === "cancelled" ? (
                    <span className="mt-1 block text-[10px] text-[var(--muted)]">No final attendance</span>
                  ) : null}
                </div>;
              },
            },
            {
              key: "action",
              header: "Action",
              align: "right",
              render: (row) => (
                <LinkButton
                  variant={row.status === "in_progress" ? "primary" : "default"}
                  href={`/lecturer/sessions/${row.sessionId}`}
                >
                  {row.status === "in_progress" ? "Monitor" : row.status === "scheduled" ? "Prepare" : row.status === "cancelled" ? "View cancelled" : "View"}
                </LinkButton>
              ),
            },
          ]}
          rows={sessions}
          getRowKey={(row) => row.sessionId}
        />
      </Card>
    </div>
  );
}
