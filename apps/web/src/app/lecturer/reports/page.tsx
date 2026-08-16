import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function LecturerReportsPage() {
  return (
    <div>
      <PageHeader title="Attendance reports" description="Analyse attendance across assigned courses and scheduled sessions." />
      <EmptyState title="Reports content lands in Stage 2" description="Attendance trend and course breakdown charts are built next." />
    </div>
  );
}
