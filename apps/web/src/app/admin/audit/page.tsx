import { PageHeader } from "@/components/ui/PageHeader";
import { AuditLogTable } from "@/components/admin/AuditLogTable";
import { getAuditLog } from "@/services/adminService";

export default async function AdminAuditPage() {
  const entries = await getAuditLog();

  return (
    <div>
      <PageHeader title="Audit log" />
      <AuditLogTable entries={entries} />
    </div>
  );
}
