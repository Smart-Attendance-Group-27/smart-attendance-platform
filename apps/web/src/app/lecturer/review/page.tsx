import { PageHeader } from "@/components/ui/PageHeader";
import { ReviewWorkspace } from "@/components/lecturer/ReviewWorkspace";
import { getReviewCases } from "@/services/lecturerService";

export default async function LecturerReviewPage() {
  const cases = await getReviewCases();

  return (
    <div>
      <PageHeader
        title="Verification review"
        description="Review uncertain verification results and authorised manual attendance requests."
      />
      <ReviewWorkspace initialCases={cases} />
    </div>
  );
}
