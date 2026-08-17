import { Card } from "@/components/ui/Card";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { AttendancePolicy } from "@/types/admin";

export function AttendancePolicyForm({ policy }: { policy: AttendancePolicy }) {
  return (
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
  );
}
