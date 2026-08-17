import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { Button } from "@/components/ui/Button";
import { UsersWorkspace } from "@/components/admin/UsersWorkspace";
import { getUserDirectory } from "@/services/adminService";

export default async function AdminUsersPage() {
  const directory = await getUserDirectory();

  return (
    <div>
      <PageHeader
        title="Users"
        description="Manage student, lecturer, and administrator accounts. Credentials remain in Keycloak — this page manages application profile and access status only."
        actions={
          <Button variant="primary" title="Available once user administration API is integrated" disabled>
            Provision account
          </Button>
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
