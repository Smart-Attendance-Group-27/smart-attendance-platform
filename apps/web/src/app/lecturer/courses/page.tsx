import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { ActivityList } from "@/components/ui/ActivityList";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { CorrectionRequestButton } from "@/components/lecturer/CorrectionRequestButton";
import { AssignedCoursesCard } from "@/components/lecturer/AssignedCoursesCard";
import { MyCorrectionRequestsCard } from "@/components/lecturer/MyCorrectionRequestsCard";
import { getLecturerCourses, getMyCorrectionRequests } from "@/services/lecturerService";
import { TimetableEntry } from "@/types/lecturer";

export default async function LecturerCoursesPage() {
  const [{ semesterLabel, courses, timetable, sourceStatus }, correctionRequests] = await Promise.all([
    getLecturerCourses(),
    getMyCorrectionRequests(),
  ]);

  return (
    <div>
      <PageHeader
        title="My courses and timetable"
        description="View authorised academic data for assigned courses."
        actions={
          <CorrectionRequestButton
            requestType="course_data"
            variant="primary"
            buttonLabel="Request data correction"
            dialogTitle="Request data correction"
            targetLabel="Course"
            targets={courses.map((course) => ({
              id: course.courseId,
              label: `${course.courseCode} · ${course.courseName}`,
            }))}
          />
        }
      />

      <Notice title="Read-only academic information.">
        Course definitions, enrolments, lecturer assignments, and timetable records are
        maintained by administrators. Corrections are submitted for administrative review.
      </Notice>

      <AssignedCoursesCard courses={courses} semesterLabel={semesterLabel} />

      <div className="mt-4">
        <MyCorrectionRequestsCard requests={correctionRequests} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card
            title="Weekly timetable"
            subtitle="Read-only"
            flush
            actions={
              <CorrectionRequestButton
                requestType="timetable"
                buttonLabel="Request timetable correction"
                dialogTitle="Request timetable correction"
                targetLabel="Timetable entry"
                targets={timetable.map((entry) => ({
                  id: entry.id,
                  label: `${entry.courseCode} · ${entry.day} ${entry.timeRange} · ${entry.room}`,
                }))}
              />
            }
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
