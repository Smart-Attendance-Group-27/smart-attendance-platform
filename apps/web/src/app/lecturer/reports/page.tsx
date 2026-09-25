import { PageHeader } from "@/components/ui/PageHeader";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ExportCsvButton } from "@/components/ui/ExportCsvButton";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart } from "@/components/charts/BarChart";
import { getLecturerReports } from "@/services/lecturerService";
import { riskLevelDisplay } from "@/lib/status";
import { AtRiskStudent } from "@/types/lecturer";

export default async function LecturerReportsPage() {
  const { summary, attendanceTrend, attendanceByCourse, atRiskStudents } = await getLecturerReports();

  return (
    <div>
      <PageHeader
        title="Attendance reports"
        description="Analyse attendance across assigned courses and scheduled sessions."
        actions={
          <ExportCsvButton
            filenamePrefix="students-below-threshold"
            label="Export at-risk list"
            headers={["Index", "Student", "Course", "Attendance (%)", "Late count", "Last attended", "Risk level"]}
            rows={atRiskStudents.map((student) => [
              student.studentIndex,
              student.studentName,
              student.courseCode,
              student.attendanceRatePercent,
              student.lateCount,
              student.lastAttendedLabel,
              student.riskLevel,
            ])}
          />
        }
      />

      <SummaryStrip
        items={[
          { label: "Overall attendance", value: `${summary.overallAttendancePercent}%`, note: "All closed sessions" },
          { label: "Sessions completed", value: summary.sessionsCompleted, note: "Closed sessions" },
          {
            label: "Average late rate",
            value: `${summary.averageLateRatePercent}%`,
            note: "Of present and late check-ins",
          },
          { label: "Students at risk", value: summary.studentsAtRiskCount, note: "Below the course threshold", noteTone: "warn" },
        ]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <Card title="Attendance trend">
            <LineChart
              data={attendanceTrend.map((point) => ({ label: point.label, value: point.attendanceRate }))}
              minValue={70}
              maxValue={100}
              ariaLabel="Attendance trend line chart"
            />
          </Card>
        </div>
        <div className="lg:col-span-5">
          <Card title="Attendance by course">
            <BarChart
              data={attendanceByCourse.map((item) => ({ label: item.courseCode, value: item.attendanceRatePercent }))}
              maxValue={100}
            />
          </Card>
        </div>
        <div className="lg:col-span-12">
          <Card
            title="Students below attendance threshold"
            flush
          >
            <DataTable<AtRiskStudent>
              emptyTitle="No students below the attendance threshold"
              emptyDescription="Great news — every student in this period is meeting the target."
              columns={[
                {
                  key: "student",
                  header: "Student",
                  render: (row) => <CellPrimary primary={row.studentName} secondary={row.studentIndex} />,
                },
                { key: "course", header: "Course", render: (row) => row.courseCode },
                { key: "attendance", header: "Attendance", render: (row) => `${row.attendanceRatePercent}%` },
                { key: "late", header: "Late count", render: (row) => row.lateCount },
                { key: "last", header: "Last attended", render: (row) => row.lastAttendedLabel },
                {
                  key: "risk",
                  header: "Risk level",
                  render: (row) => {
                    const display = riskLevelDisplay(row.riskLevel);
                    return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
                  },
                },
              ]}
              rows={atRiskStudents}
              getRowKey={(row) => row.studentId}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
