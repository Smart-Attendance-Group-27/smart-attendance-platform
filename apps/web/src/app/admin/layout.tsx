import { requireRole } from "@/lib/auth/dal";
import { DashboardShell } from "@/components/layout/DashboardShell";

export default async function AdminLayout(props: LayoutProps<"/admin">) {
  const session = await requireRole("administrator");

  return (
    <DashboardShell userName={session.name} role="administrator">
      {props.children}
    </DashboardShell>
  );
}
