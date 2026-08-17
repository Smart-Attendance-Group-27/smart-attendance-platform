import { PageHeader } from "@/components/ui/PageHeader";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { Card } from "@/components/ui/Card";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
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
          <>
            <Button title="Available once the report export API is integrated" disabled>
              Export CSV
            </Button>
            <Button variant="primary" title="Available once the report export API is integrated" disabled>
              Generate PDF report
            </Button>
          </>
        }
      />

      <div className="mb-4 border border-[var(--line)]">
        <FilterBar>
          <FilterSelect>
            <option>Semester 2 · 2026</option>
          </FilterSelect>
          <FilterSelect>
            <option>All assigned courses</option>
          </FilterSelect>
          <input type="date" defaultValue="2026-07-01" className="h-8 border border-[#c8d0d7] bg-white px-2.5 text-[11px] text-[#33414c]" />
          <input type="date" defaultValue="2026-07-31" className="h-8 border border-[#c8d0d7] bg-white px-2.5 text-[11px] text-[#33414c]" />
          <Button variant="primary">Update report</Button>
        </FilterBar>
      </div>

      <SummaryStrip
        items={[
          { label: "Overall attendance", value: `${summary.overallAttendancePercent}%`, note: "Target met", noteTone: "good" },
          { label: "Sessions completed", value: summary.sessionsCompleted, note: "Selected period" },
          {
            label: "Average late rate",
            value: `${summary.averageLateRatePercent}%`,
            note: `Down ${Math.abs(summary.averageLateRateDeltaPercent)}%`,
            noteTone: "good",
          },
          { label: "Students at risk", value: summary.studentsAtRiskCount, note: "Below 70% attendance", noteTone: "warn" },
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
            actions={
              <a href="#" className="text-[11px] text-[var(--link)]">
                View all {summary.studentsAtRiskCount}
              </a>
            }
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
