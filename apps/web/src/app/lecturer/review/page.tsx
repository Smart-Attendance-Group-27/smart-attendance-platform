import { PageHeader } from "@/components/ui/PageHeader";
import { ReviewWorkspace } from "@/components/lecturer/ReviewWorkspace";
import { getReviewCases } from "@/services/lecturerService";

export default async function LecturerReviewPage() {
  const cases = await getReviewCases();

  return (
    <div>
      <PageHeader
        title="Verification review"
      />
      <ReviewWorkspace initialCases={cases} />
    </div>
  );
}
