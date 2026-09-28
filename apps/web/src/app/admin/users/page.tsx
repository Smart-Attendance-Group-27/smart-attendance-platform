import { PageHeader } from "@/components/ui/PageHeader";
import { UsersWorkspace } from "@/components/admin/UsersWorkspace";
import { ProvisionAccountButton } from "@/components/admin/ProvisionAccountButton";
import { getProvisioningDepartments, getUserDirectory } from "@/services/adminService";

export default async function AdminUsersPage() {
  const [directory, departments] = await Promise.all([
    getUserDirectory(),
    getProvisioningDepartments(),
  ]);

  return (
    <div>
      <PageHeader
        title="Users"
        actions={
          <ProvisionAccountButton departments={departments} />
        }
      />
      <UsersWorkspace directory={directory} />
    </div>
  );
}
