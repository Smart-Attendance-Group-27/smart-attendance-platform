import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function LecturerSessionsPage() {
  return (
    <div>
      <PageHeader title="Attendance sessions" description="View and monitor your attendance sessions." />
      <EmptyState title="Sessions content lands in Stage 2" description="Session list and the live session monitor are built next." />
    </div>
  );
}
