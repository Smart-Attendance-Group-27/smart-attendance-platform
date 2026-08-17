import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { ActivityList } from "@/components/ui/ActivityList";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { LinkButton } from "@/components/ui/LinkButton";
import { LineChart } from "@/components/charts/LineChart";
import { getLecturerOverview } from "@/services/lecturerService";
import { sessionStatusDisplay } from "@/lib/status";
import { TodayLecture } from "@/types/lecturer";

export default async function LecturerDashboardPage() {
  const { summary, todayLectures, attentionItems, weeklyTrend, recentActivity } = await getLecturerOverview();
  const nextOpenSession = todayLectures.find((lecture) => lecture.status === "in_progress");

  return (
    <div>
      <PageHeader
        title="Attendance overview"
        description="Current lecture activity and items requiring attention."
        actions={
          <>
            <LinkButton href="/lecturer/courses">View timetable</LinkButton>
            {nextOpenSession ? (
              <LinkButton variant="primary" href={`/lecturer/sessions/${nextOpenSession.sessionId}`}>
                Open active session
              </LinkButton>
            ) : (
              <Button variant="primary" disabled>
                Open active session
              </Button>
            )}
          </>
        }
      />

      <Notice title="Academic data source:">
        Courses, enrolments, lecturer assignments, and timetable entries are synchronised from
        authorised University systems. Lecturers have read-only access to these records.
      </Notice>

      <SummaryStrip
        aria-label="Today's attendance summary"
        items={[
          {
            label: "Active lectures",
            value: summary.activeLectures,
            note: `${summary.checkInWindowsOpen} check-in windows open`,
            noteTone: "good",
          },
          {
            label: "Students checked in",
            value: summary.studentsCheckedIn,
            note: "Across today's sessions",
          },
          {
            label: "Pending review",
            value: summary.pendingReview,
            note: `${summary.pendingReviewNeedingAction} need lecturer action`,
            noteTone: "warn",
          },
          {
            label: "Attendance rate",
            value: `${summary.attendanceRatePercent}%`,
            note: `Up ${summary.attendanceRateDeltaPercent}% from last week`,
            noteTone: "good",
          },
        ]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card title="Today's scheduled lectures" subtitle="Generated from the academic timetable" flush>
            <DataTable<TodayLecture>
              emptyTitle="No lectures scheduled today"
              emptyDescription="Sessions generated from the academic timetable will appear here."
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
              rows={todayLectures}
              getRowKey={(row) => row.sessionId}
            />
          </Card>
        </div>

        <div className="lg:col-span-4">
          <Card
            title="Items requiring attention"
            actions={
              <a href="/lecturer/review" className="text-[11px] text-[var(--link)]">
                Open review queue
              </a>
            }
          >
            <ActivityList
              emptyTitle="Nothing needs your attention right now"
              items={attentionItems.map((item) => ({
                id: item.id,
                time: item.time,
                title: item.title,
                detail: item.detail,
                status: (
                  <StatusBadge tone={item.severity === "danger" ? "danger" : item.severity === "warning" ? "warning" : "info"}>
                    {item.severity === "info" ? "Pending" : "Review"}
                  </StatusBadge>
                ),
              }))}
            />
          </Card>
        </div>

        <div className="lg:col-span-7">
          <Card title="Weekly attendance trend" subtitle="Assigned courses">
            <LineChart
              data={weeklyTrend.map((point) => ({ label: point.label, value: point.attendanceRate }))}
              minValue={70}
              maxValue={100}
              ariaLabel="Weekly attendance trend line chart"
            />
          </Card>
        </div>

        <div className="lg:col-span-5">
          <Card title="Recent session activity">
            <ActivityList
              emptyTitle="No session activity yet today"
              items={recentActivity.map((item) => ({
                id: item.id,
                time: item.time,
                title: item.title,
                detail: item.detail,
                status: (
                  <StatusBadge tone={item.tag === "qr" ? "purple" : item.tag === "success" ? "success" : "info"}>
                    {item.tag === "qr" ? "QR" : item.tag === "success" ? "Complete" : "Logged"}
                  </StatusBadge>
                ),
              }))}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
