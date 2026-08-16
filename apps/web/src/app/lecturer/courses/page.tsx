import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function LecturerCoursesPage() {
  return (
    <div>
      <PageHeader title="My courses and timetable" description="View authorised academic data for assigned courses." />
      <EmptyState title="Courses content lands in Stage 2" description="Assigned course list and weekly timetable are built next." />
    </div>
  );
}
