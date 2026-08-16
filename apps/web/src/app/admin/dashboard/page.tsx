import { PageHeader } from "@/components/ui/PageHeader";
import { Notice } from "@/components/ui/Notice";
import { SummaryStrip } from "@/components/ui/SummaryStrip";
import { Card } from "@/components/ui/Card";
import { ActivityList } from "@/components/ui/ActivityList";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { ClassroomGeofencePanel } from "@/components/admin/ClassroomGeofencePanel";
import { getAdminDashboard } from "@/services/adminService";
import { syncStatusDisplay } from "@/lib/status";

export default async function AdminDashboardPage() {
  const { summary, classrooms, policy, academicSync } = await getAdminDashboard();

  return (
    <div>
      <PageHeader
        title="Administration"
        description="Institutional user, academic-source, classroom, geofence, and attendance-policy controls."
        actions={
          <Button variant="primary" title="Available once the policy configuration API is integrated" disabled>
            Save changes
          </Button>
        }
      />

      <Notice variant="warning" title="Administrator-only controls.">
        Institutional geofences, attendance policies, user access, and academic-source
        synchronisation can only be changed by authorised administrators.
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
            noteTone: "good",
          },
          { label: "Policy alerts", value: summary.policyAlertsCount, note: "Review recommended", noteTone: "warn" },
        ]}
      />

      <ClassroomGeofencePanel classrooms={classrooms} />

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <Card title="Default attendance and verification policy" className="border-l-4 border-l-[var(--uom-gold)]">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormField
                label="Check-in window duration"
                htmlFor="checkin"
                help="Time provided for the initial face and location verification."
              >
                <input id="checkin" defaultValue={`${policy.checkInWindowMinutes} minutes`} className={fieldInputClassName()} />
              </FormField>
              <FormField
                label="Late threshold"
                htmlFor="late"
                help="Time after the check-in boundary before attendance is recorded as late."
              >
                <input id="late" defaultValue={`${policy.lateThresholdMinutes} minutes`} className={fieldInputClassName()} />
              </FormField>
              <FormField
                label="Face verification confidence threshold"
                htmlFor="confidence"
                help="Submissions below this value enter the verification review queue."
              >
                <input id="confidence" defaultValue={`${policy.faceConfidenceThresholdPercent}%`} className={fieldInputClassName()} />
              </FormField>
              <FormField
                label="Additional face-check policy"
                htmlFor="additional"
                help="Additional checks are separate from the initial attendance check-in."
              >
                <select id="additional" defaultValue={policy.additionalFaceCheckPolicyLabel} className={fieldInputClassName()}>
                  <option>{policy.additionalFaceCheckPolicyLabel}</option>
                </select>
              </FormField>
              <FormField
                label="Dynamic QR verification"
                htmlFor="qr"
                help="Lecturers may run zero or multiple QR windows during a lecture."
              >
                <select id="qr" defaultValue={policy.dynamicQrPolicyLabel} className={fieldInputClassName()}>
                  <option>{policy.dynamicQrPolicyLabel}</option>
                </select>
              </FormField>
              <FormField label="QR window duration" htmlFor="expiry" help="Maximum validity of an optional QR verification event.">
                <input id="expiry" defaultValue={`${policy.qrWindowMinutes} minutes`} className={fieldInputClassName()} />
              </FormField>
            </div>
          </Card>
        </div>

        <div className="lg:col-span-5">
          <Card
            title="Academic-data synchronisation"
            className="border-l-4 border-l-[var(--uom-gold)]"
            actions={
              <Button title="Available once academic-source sync API is integrated" disabled>
                Run sync
              </Button>
            }
          >
            <ActivityList
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
