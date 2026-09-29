import Link from "next/link";
import { ReferenceFaceEnrollmentForm } from "@/components/admin/ReferenceFaceEnrollmentForm";
import { ReferenceFaceTable } from "@/components/admin/ReferenceFaceTable";
import { buttonClassName } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { isWebMockMode } from "@/lib/api/mode";
import { getReferenceFaces } from "@/services/adminService";

export default async function AdminFaceEnrolmentPage() {
  const referenceFaces = await getReferenceFaces();

  return (
    <div>
      <PageHeader
        title="Face enrolment"
        actions={
          <Link href="/admin/users" className={buttonClassName()}>
            Back to users
          </Link>
        }
      />
      <div className="flex flex-col gap-4">
        <ReferenceFaceEnrollmentForm readOnly={isWebMockMode()} />
        <ReferenceFaceTable records={referenceFaces} />
      </div>
    </div>
  );
}
