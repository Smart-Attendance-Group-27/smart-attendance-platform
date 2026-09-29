import Link from "next/link";
import { PageHeader } from "@/components/ui/PageHeader";
import { buttonClassName } from "@/components/ui/Button";
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
          <>
            <Link href="/admin/users/face-enrolment" className={buttonClassName("primary")}>
              Face enrolment
            </Link>
            <ProvisionAccountButton departments={departments} />
          </>
        }
      />
      <UsersWorkspace directory={directory} />
    </div>
  );
}
