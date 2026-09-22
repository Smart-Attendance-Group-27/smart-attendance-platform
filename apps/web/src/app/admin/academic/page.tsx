import { PageHeader } from "@/components/ui/PageHeader";
import { AcademicDataWorkspace } from "@/components/admin/AcademicDataWorkspace";
import { getAcademicData, getAcademicReferenceData } from "@/services/adminService";

export default async function AdminAcademicPage() {
  const [data, references] = await Promise.all([
    getAcademicData(),
    getAcademicReferenceData(),
  ]);

  return (
    <div>
      <PageHeader
        title="Academic data"
        description="Courses, offerings, timetables, and enrolments. Lecturers see only the subset assigned to them."
      />
      <AcademicDataWorkspace data={data} references={references} />
    </div>
  );
}
