import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function LecturerReviewPage() {
  return (
    <div>
      <PageHeader
        title="Verification review"
        description="Review uncertain verification results and authorised manual attendance requests."
      />
      <EmptyState title="Review queue lands in Stage 2" description="The master-detail review workflow is built next." />
    </div>
  );
}
