import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { Card } from "@/components/ui/Card";
import { ActivityList } from "@/components/ui/ActivityList";
import { StatusBadge } from "@/components/ui/StatusBadge";
import Link from "next/link";
import { ClassroomGeofencePanel } from "@/components/admin/ClassroomGeofencePanel";
import { AttendancePolicyForm } from "@/components/admin/AttendancePolicyForm";
import { getAdminDashboard } from "@/services/adminService";
import { syncStatusDisplay } from "@/lib/status";

export default async function AdminDashboardPage() {
  const { summary, classrooms, policy, academicSync } = await getAdminDashboard();

  return (
    <div>
      <PageHeader
        title="Administration"
        description="Institutional user, academic-source, classroom, geofence, and attendance-policy controls."
        actions={<Link href="/admin/policies" className="text-xs text-[var(--link)] hover:underline">Edit attendance policy</Link>}
      />

      <Notice variant="warning" title="Administrator-only controls.">
        Institutional geofences, attendance policies, user access, and academic data
        can only be changed by authorised administrators.
      </Notice>

      <SummaryStrip
        items={[
          { label: "Active users", value: summary.activeUsersCount.toLocaleString(), note: "Students and staff" },
          {
            label: "Configured classrooms",
            value: summary.configuredClassroomsCount,
            note: `${summary.activeGeofencesCount} active geofences`,
            noteTone: "good",
          },
          {
            label: "Academic source status",
            value: <span className="text-lg">{summary.academicSourceStatusLabel}</span>,
            note: summary.lastSyncLabel,
          },
          {
            label: "Policy alerts",
            value: summary.policyAlertsCount,
            note: summary.policyAlertsCount > 0 ? "Review recommended" : "No alerts",
            noteTone: summary.policyAlertsCount > 0 ? "warn" : "neutral",
          },
        ]}
      />

      <ClassroomGeofencePanel classrooms={classrooms} />

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <AttendancePolicyForm policy={policy} readOnly />
        </div>

        <div className="lg:col-span-5">
          <Card
            title="Academic-data synchronisation"
            className="border-l-4 border-l-[var(--uom-gold)]"
          >
            <ActivityList
              emptyTitle="No synchronisation activity yet"
              items={academicSync.map((item) => {
                const display = syncStatusDisplay(item.status);
                return {
                  id: item.id,
                  time: item.time,
                  title: item.title,
                  detail: item.detail,
                  status: <StatusBadge tone={display.tone}>{display.label}</StatusBadge>,
                };
              })}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
