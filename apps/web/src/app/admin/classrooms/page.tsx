import { PageHeader } from "@/components/ui/PageHeader";
import { ClassroomsWorkspace } from "@/components/admin/ClassroomsWorkspace";
import { getAdminDashboard } from "@/services/adminService";

export default async function AdminClassroomsPage() {
  const { classrooms } = await getAdminDashboard();

  return (
    <div>
      <PageHeader
        title="Classrooms"
        description="Configure classrooms and their geofence boundaries. Editing a classroom's geofence only affects future sessions — attendance evidence from past sessions uses a frozen snapshot and is never rewritten."
      />
      <ClassroomsWorkspace classrooms={classrooms} />
    </div>
  );
}
