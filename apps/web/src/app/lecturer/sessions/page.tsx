import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LinkButton } from "@/components/ui/LinkButton";
import { getSessionList } from "@/services/lecturerService";
import { sessionStatusDisplay } from "@/lib/status";
import { TodayLecture } from "@/types/lecturer";

export default async function LecturerSessionsPage() {
  const sessions = await getSessionList();

  return (
    <div>
      <PageHeader title="Attendance sessions" description="View and monitor your attendance sessions." />

      <Card flush>
        <DataTable<TodayLecture>
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
              header: "Attendance",
              render: (row) => `${row.presentCount} / ${row.enrolledCount}`,
            },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = sessionStatusDisplay(row.status);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
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
                  {row.status === "in_progress" ? "Monitor" : row.status === "scheduled" ? "Prepare" : "View"}
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
