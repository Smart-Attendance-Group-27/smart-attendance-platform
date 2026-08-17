import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { AttendancePolicyForm } from "@/components/admin/AttendancePolicyForm";
import { ReferenceFaceTable } from "@/components/admin/ReferenceFaceTable";
import { getAdminDashboard, getReferenceFaces } from "@/services/adminService";

export default async function AdminPoliciesPage() {
  const [{ policy }, referenceFaces] = await Promise.all([getAdminDashboard(), getReferenceFaces()]);

  return (
    <div>
      <PageHeader
        title="Attendance policy and reference-face governance"
        description="Institution-wide verification defaults and student face-enrolment oversight."
        actions={
          <Button variant="primary" title="Available once the policy configuration API is integrated" disabled>
            Save changes
          </Button>
        }
      />
      <div className="flex flex-col gap-4">
        <AttendancePolicyForm policy={policy} />
        <ReferenceFaceTable records={referenceFaces} />
      </div>
    </div>
  );
}
