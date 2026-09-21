import { PageHeader } from "@/components/ui/PageHeader";
import { AttendancePolicyForm } from "@/components/admin/AttendancePolicyForm";
import { ReferenceFaceTable } from "@/components/admin/ReferenceFaceTable";
import { getAttendancePolicy, getReferenceFaces } from "@/services/adminService";
import { isWebMockMode } from "@/lib/api/mode";

export default async function AdminPoliciesPage() {
  const [policy, referenceFaces] = await Promise.all([getAttendancePolicy(), getReferenceFaces()]);

  return (
    <div>
      <PageHeader
        title="Attendance policy and reference-face governance"
        description="Institution-wide verification defaults and student face-enrolment oversight."
      />
      <div className="flex flex-col gap-4">
        <AttendancePolicyForm key={policy.updatedAt} policy={policy} readOnly={isWebMockMode()} />
        <ReferenceFaceTable records={referenceFaces} />
      </div>
    </div>
  );
}
