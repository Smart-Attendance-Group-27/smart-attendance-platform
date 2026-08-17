import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { AuditLogTable } from "@/components/admin/AuditLogTable";
import { getAuditLog } from "@/services/adminService";

export default async function AdminAuditPage() {
  const entries = await getAuditLog();

  return (
    <div>
      <PageHeader
        title="Audit log"
        description="A record of sensitive lecturer and administrator actions: manual attendance overrides, session actions, geofence and policy changes, and account changes."
      />
      <Notice variant="warning" title="Preview data.">
        The database has an `audit.audit_logs` table ready to receive these records, but no backend code
        writes to it yet — the entries below illustrate the intended UI ahead of that instrumentation
        being added.
      </Notice>
      <AuditLogTable entries={entries} />
    </div>
  );
}
