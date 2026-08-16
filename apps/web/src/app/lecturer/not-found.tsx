import { EmptyState } from "@/components/ui/EmptyState";
import { LinkButton } from "@/components/ui/LinkButton";

export default function LecturerNotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="This item may have been closed or the link may be out of date."
      action={<LinkButton href="/lecturer/dashboard">Back to overview</LinkButton>}
    />
  );
}
