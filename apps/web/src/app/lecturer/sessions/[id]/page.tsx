import { notFound } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { FilterBar, SearchInput, FilterSelect } from "@/components/ui/FilterBar";
import { DataTable, CellPrimary } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { LinkButton } from "@/components/ui/LinkButton";
import { MOCK_SESSION_DETAILS } from "@/mocks/lecturer";
import { finalStatusDisplay, verificationOutcomeDisplay, verificationOutcomeLabel } from "@/lib/status";
import { SessionStudentRow } from "@/types/lecturer";

function VerificationCell({ outcome }: { outcome: SessionStudentRow["initialFaceCheck"] }) {
  const display = verificationOutcomeDisplay(outcome);
  if (!display) return <span className="text-[var(--muted)]">{verificationOutcomeLabel(outcome)}</span>;
  return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
}

export default async function SessionMonitorPage(props: PageProps<"/lecturer/sessions/[id]">) {
  const { id } = await props.params;
  const session = MOCK_SESSION_DETAILS[id];

  if (!session) {
    notFound();
  }

  const isActive = session.status === "in_progress";

  return (
    <div>
      <PageHeader
        title="Live session monitor"
        description={`${session.courseCode} · ${session.courseName} · ${session.room}`}
        actions={
          isActive ? (
            <Button variant="danger">Close session</Button>
          ) : (
            <StatusBadge tone="neutral">Session closed</StatusBadge>
          )
        }
      />

      <Card flush>
        <div className="grid grid-cols-1 border-b border-[var(--line)] sm:grid-cols-2 lg:grid-cols-[1.3fr_repeat(4,minmax(120px,1fr))]">
          <div className="border-b border-[var(--line-soft)] p-4 lg:border-b-0 lg:border-r">
            <p className="text-lg font-semibold text-[#2d3d49]">
              {session.courseCode} {session.courseName}
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">{session.startedAtLabel}</p>
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

        <div className="flex flex-wrap gap-1.5 border-b border-[var(--line)] bg-[#fafbfc] p-2.5">
          <Button disabled={!isActive}>Start additional face check</Button>
          <Button disabled={!isActive} className="gap-2">
            Launch QR verification <StatusBadge tone="purple">Optional</StatusBadge>
          </Button>
          <Button disabled={!isActive}>Pause check-in</Button>
          <Button>Session policy</Button>
        </div>

        <SummaryStrip
          items={[
            { label: "Present", value: session.summary.presentCount, note: `${session.summary.presentPercent}%`, noteTone: "good" },
            { label: "Late", value: session.summary.lateCount, note: `${session.summary.latePercent}%`, noteTone: "warn" },
            { label: "Pending review", value: session.summary.pendingReviewCount, note: "Manual decision required", noteTone: "warn" },
            { label: "Not verified", value: session.summary.notVerifiedCount, note: `${session.summary.notVerifiedPercent}%` },
          ]}
        />

        <FilterBar>
          <SearchInput placeholder="Search by name or student ID" />
          <FilterSelect>
            <option>All attendance states</option>
          </FilterSelect>
          <FilterSelect>
            <option>All verification events</option>
          </FilterSelect>
          <Button>Apply filters</Button>
        </FilterBar>

        {session.students.length === 0 ? (
          <p className="p-6 text-center text-xs text-[var(--muted)]">
            No students have checked in yet — this session has not opened its check-in window.
          </p>
        ) : (
          <DataTable<SessionStudentRow>
            columns={[
              {
                key: "student",
                header: "Student",
                render: (row) => <CellPrimary primary={`Student ${row.studentIndex}`} secondary={row.studentIndex} />,
              },
              { key: "initial", header: "Initial face check", render: (row) => <VerificationCell outcome={row.initialFaceCheck} /> },
              { key: "additional", header: "Additional check", render: (row) => <VerificationCell outcome={row.additionalCheck} /> },
              { key: "qr", header: "QR verification", render: (row) => <VerificationCell outcome={row.qrVerification} /> },
              {
                key: "final",
                header: "Final status",
                render: (row) => {
                  const display = finalStatusDisplay(row.finalStatus);
                  return <StatusBadge tone={display.tone}>{display.label}</StatusBadge>;
                },
              },
              { key: "time", header: "Time", render: (row) => row.time },
              {
                key: "action",
                header: "Action",
                align: "right",
                render: (row) =>
                  row.finalStatus === "pending_review" ? (
                    <LinkButton href="/lecturer/review">Review</LinkButton>
                  ) : (
                    <span className="text-[var(--muted)]">—</span>
                  ),
              },
            ]}
            rows={session.students}
            getRowKey={(row) => row.studentId}
          />
        )}
      </Card>
    </div>
  );
}
