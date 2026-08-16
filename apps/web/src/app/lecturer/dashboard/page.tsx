import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function LecturerDashboardPage() {
  return (
    <div>
      <PageHeader title="Attendance overview" description="Current lecture activity and items requiring attention." />
      <EmptyState
        title="Overview content lands in Stage 2"
        description="This route is wired up (layout, nav, guard) as part of the dashboard foundation. Today's lectures, attendance summary, and trend charts are built next."
      />
    </div>
  );
}
