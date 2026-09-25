import { PageHeader } from "@/components/ui/PageHeader";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ExportCsvButton } from "@/components/ui/ExportCsvButton";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart } from "@/components/charts/BarChart";
import { getInstitutionReports } from "@/services/adminService";
import { AtRiskCourse } from "@/types/admin";

export default async function AdminReportsPage() {
  const { summary, attendanceTrend, attendanceByFaculty, atRiskCourses } = await getInstitutionReports();

  return (
    <div>
      <PageHeader
        title="Institution reports"
        description="University-wide attendance analytics across every faculty and course."
        actions={
          <ExportCsvButton
            filenamePrefix="courses-below-threshold"
            label="Export at-risk courses"
            headers={["Code", "Course", "Attendance (%)"]}
            rows={atRiskCourses.map((course) => [course.courseCode, course.courseName, course.attendanceRatePercent])}
          />
        }
      />

      <SummaryStrip
        items={[
          { label: "Overall attendance", value: `${summary.overallAttendancePercent}%`, note: "All closed sessions" },
          { label: "Closed sessions", value: summary.totalSessionsCompleted.toLocaleString() },
          { label: "Students", value: summary.totalStudents.toLocaleString() },
          { label: "Students at risk", value: summary.studentsAtRiskCount, note: "Below course threshold", noteTone: "warn" },
        ]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <Card title="Attendance trend">
            <LineChart
              data={attendanceTrend.map((point) => ({ label: point.label, value: point.attendanceRate }))}
              minValue={70}
              maxValue={100}
              ariaLabel="Institution attendance trend line chart"
            />
          </Card>
        </div>
        <div className="lg:col-span-5">
          <Card title="Attendance by faculty">
            <BarChart
              data={attendanceByFaculty.map((item) => ({ label: item.facultyName, value: item.attendanceRatePercent }))}
              maxValue={100}
            />
          </Card>
        </div>
        <div className="lg:col-span-12">
          <Card title="Courses below attendance threshold" flush>
            <DataTable<AtRiskCourse>
              emptyTitle="No courses below threshold"
              columns={[
                { key: "code", header: "Code", render: (row) => <span className="font-semibold text-[var(--link)]">{row.courseCode}</span> },
                { key: "name", header: "Course", render: (row) => row.courseName },
                {
                  key: "rate",
                  header: "Attendance rate",
                  render: (row) => (
                    <StatusBadge tone={row.attendanceRatePercent < 70 ? "danger" : "warning"}>
                      {row.attendanceRatePercent}%
                    </StatusBadge>
                  ),
                },
              ]}
              rows={atRiskCourses}
              getRowKey={(row) => row.courseCode}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
