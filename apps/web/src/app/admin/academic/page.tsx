import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { Button } from "@/components/ui/Button";
import { AcademicDataWorkspace } from "@/components/admin/AcademicDataWorkspace";
import { getAcademicData } from "@/services/adminService";

export default async function AdminAcademicPage() {
  const data = await getAcademicData();

  return (
    <div>
      <PageHeader
        title="Academic data"
        description="Courses, offerings, timetables, and enrolments. Lecturers see only the subset assigned to them."
        actions={
          <Button title="External academic source integration not configured" disabled>
            Run sync
          </Button>
        }
      />
      {data.sourceConnectionStatus === "not_configured" ? (
        <Notice variant="warning" title="External academic source integration not configured.">
          No university LMS/SIS connector is set up. The records below are the locally available academic
          data — synchronisation from an external source will appear here once one is configured.
        </Notice>
      ) : null}
      <AcademicDataWorkspace data={data} />
    </div>
  );
}
