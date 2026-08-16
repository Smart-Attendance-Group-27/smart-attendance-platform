import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function AdminDashboardPage() {
  return (
    <div>
      <PageHeader
        title="Administration"
        description="Institutional user, academic-source, classroom, geofence, and attendance-policy controls."
      />
      <EmptyState
        title="Administration content lands in Stage 3"
        description="Classrooms/geofences, default attendance policy, and academic-data sync status are built next."
      />
    </div>
  );
}
