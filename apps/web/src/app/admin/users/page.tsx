import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
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
        description="Manage student, lecturer, and administrator accounts. Credentials remain in Keycloak — this page manages application profile and access status only."
        actions={
          <ProvisionAccountButton departments={departments} />
        }
      />
      <Notice>
        Passwords and sign-in credentials are never stored here — Keycloak remains the identity provider.
        This page manages each account&apos;s application profile and access status.
      </Notice>
      <UsersWorkspace directory={directory} />
    </div>
  );
}
