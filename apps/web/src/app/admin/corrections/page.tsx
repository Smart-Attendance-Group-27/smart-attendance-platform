import { PageHeader } from "@/components/ui/PageHeader";
import { CorrectionRequestsWorkspace } from "@/components/admin/CorrectionRequestsWorkspace";
import { getCorrectionRequests } from "@/services/adminService";

export default async function AdminCorrectionsPage() {
  const requests = await getCorrectionRequests();

  return (
    <div>
      <PageHeader title="Correction requests" />
      <CorrectionRequestsWorkspace requests={requests} />
    </div>
  );
}
