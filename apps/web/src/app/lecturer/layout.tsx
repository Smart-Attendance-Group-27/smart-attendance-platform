import { requireRole } from "@/lib/auth/dal";
import { DashboardShell } from "@/components/layout/DashboardShell";

export default async function LecturerLayout(props: LayoutProps<"/lecturer">) {
  const session = await requireRole("lecturer");

  return (
    <DashboardShell userName={session.name} role="lecturer">
      {props.children}
    </DashboardShell>
  );
}
