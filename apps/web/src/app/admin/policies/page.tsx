import { PageHeader } from "@/components/ui/PageHeader";
import { AttendancePolicyForm } from "@/components/admin/AttendancePolicyForm";
import { getAttendancePolicy } from "@/services/adminService";
import { isWebMockMode } from "@/lib/api/mode";

export default async function AdminPoliciesPage() {
  const policy = await getAttendancePolicy();

  return (
    <div>
      <PageHeader
        title="Attendance policy and reference-face governance"
      />
      <div className="flex flex-col gap-4">
        <AttendancePolicyForm key={policy.updatedAt} policy={policy} readOnly={isWebMockMode()} />
      </div>
    </div>
  );
}
