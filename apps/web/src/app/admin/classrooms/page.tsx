import { PageHeader } from "@/components/ui/PageHeader";
import { ClassroomsWorkspace } from "@/components/admin/ClassroomsWorkspace";
import { getAdminDashboard, getBuildingOptions } from "@/services/adminService";

export default async function AdminClassroomsPage() {
  const [{ classrooms }, buildings] = await Promise.all([getAdminDashboard(), getBuildingOptions()]);

  return (
    <div>
      <PageHeader title="Classrooms" />
      <ClassroomsWorkspace classrooms={classrooms} buildings={buildings} />
    </div>
  );
}
