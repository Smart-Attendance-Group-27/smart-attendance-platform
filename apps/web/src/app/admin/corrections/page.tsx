import { PageHeader } from "@/components/ui/PageHeader";
import { CorrectionRequestsWorkspace } from "@/components/admin/CorrectionRequestsWorkspace";
import { getCorrectionRequests } from "@/services/adminService";

export default async function AdminCorrectionsPage() {
  const requests = await getCorrectionRequests();

  return (
    <div>
      <PageHeader
        title="Correction requests"
        description="Review corrections lecturers have asked for in course data and timetables. Approving a request does not change the record; make the change in Academic data and then mark the request resolved."
      />
      <CorrectionRequestsWorkspace requests={requests} />
    </div>
  );
}
