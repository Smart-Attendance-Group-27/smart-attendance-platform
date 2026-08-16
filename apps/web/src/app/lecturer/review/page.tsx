import { PageHeader } from "@/components/ui/PageHeader";
import { ReviewWorkspace } from "@/components/lecturer/ReviewWorkspace";
import { MOCK_REVIEW_CASES } from "@/mocks/lecturer";

export default function LecturerReviewPage() {
  return (
    <div>
      <PageHeader
        title="Verification review"
        description="Review uncertain verification results and authorised manual attendance requests."
      />
      <ReviewWorkspace initialCases={MOCK_REVIEW_CASES} />
    </div>
  );
}
