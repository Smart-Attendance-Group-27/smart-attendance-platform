import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { ActivityList } from "@/components/ui/ActivityList";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { getLecturerCourses } from "@/services/lecturerService";
import { courseStatusDisplay } from "@/lib/status";
import { LecturerCourse, TimetableEntry } from "@/types/lecturer";

export default async function LecturerCoursesPage() {
  const { semesterLabel, courses, timetable, sourceStatus } = await getLecturerCourses();

  return (
    <div>
      <PageHeader
        title="My courses and timetable"
        description="View authorised academic data for assigned courses."
        actions={<Button variant="primary">Request data correction</Button>}
      />

      <Notice title="Read-only academic information.">
        Course definitions, enrolments, lecturer assignments, and timetable records are
        maintained through authorised University systems. Corrections are submitted for
        administrative review.
      </Notice>

      <Card
        title="Assigned courses"
        subtitle={semesterLabel}
        flush
        actions={
          <>
            <Button>Filter</Button>
            <Button>Export list</Button>
          </>
        }
      >
        <DataTable<LecturerCourse>
          emptyTitle="No assigned courses yet"
          emptyDescription="Courses synchronised from University systems will appear here."
          columns={[
            { key: "code", header: "Code", render: (row) => <span className="font-semibold text-[var(--link)]">{row.courseCode}</span> },
            {
              key: "course",
              header: "Course",
              render: (row) => <CellPrimary primary={row.courseName} secondary={row.scheduleSummary} />,
            },
            { key: "lecturer", header: "Lecturer", render: (row) => row.lecturerName },
            { key: "enrolled", header: "Enrolled", render: (row) => row.enrolledCount },
            { key: "attendance", header: "Attendance", render: (row) => `${row.attendanceRatePercent}%` },
            {
              key: "status",
              header: "Status",
              render: (row) => {
                const display = courseStatusDisplay(row.status);
                return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
              },
            },
          ]}
          rows={courses}
          getRowKey={(row) => row.courseId}
        />
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card
            title="Weekly timetable"
            subtitle="Read-only"
            flush
            actions={<Button>Request timetable correction</Button>}
          >
            <DataTable<TimetableEntry>
              emptyTitle="No timetable entries yet"
              columns={[
                { key: "day", header: "Day", render: (row) => row.day },
                { key: "time", header: "Time", render: (row) => row.timeRange },
                {
                  key: "course",
                  header: "Course",
                  render: (row) => (
                    <span className="font-semibold text-[var(--link)]">
                      {row.courseCode} {row.courseName}
                    </span>
                  ),
                },
                { key: "room", header: "Room", render: (row) => row.room },
                { key: "source", header: "Academic source", render: (row) => row.source },
              ]}
              rows={timetable}
              getRowKey={(row) => row.id}
            />
          </Card>
        </div>

        <div className="lg:col-span-4">
          <Card title="Source status">
            <ActivityList
              emptyTitle="No sync activity yet"
              items={sourceStatus.map((item) => ({
                id: item.id,
                time: item.time,
                title: item.title,
                detail: item.detail,
                status: (
                  <StatusBadge tone={item.status === "current" ? "success" : "warning"}>
                    {item.status === "current" ? "Current" : "Review"}
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
