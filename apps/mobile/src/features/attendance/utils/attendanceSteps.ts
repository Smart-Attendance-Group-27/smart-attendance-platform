import type { QrProgress } from '../../qr/types/qrProgress';
import type { FinalAttendanceStatus, MyAttendance } from '../types/myAttendance';

// Display states only. Whether a step counts is decided by the server; this
// file only turns the server's evidence and policy into what the screen shows.
export type StepState =
  | 'pending'
  | 'active'
  | 'processing'
  | 'passed'
  | 'failed'
  | 'waived'
  | 'partial'
  | 'not_required';

export type AttendanceStepKey = 'location' | 'face' | 'qr' | 'attendance';

export type AttendanceStep = {
  readonly key: AttendanceStepKey;
  readonly title: string;
  readonly state: StepState;
  readonly detail: string;
};

export type SummaryTone = 'success' | 'warning' | 'error' | 'info' | 'neutral';

export type AttendanceSummary = {
  readonly title: string;
  readonly message: string;
  readonly tone: SummaryTone;
};

export const STEP_STATE_LABELS: Record<StepState, string> = {
  pending: 'Pending',
  active: 'Action needed',
  processing: 'In progress',
  passed: 'Completed',
  failed: 'Failed',
  waived: 'Waived',
  partial: 'Partial',
  not_required: 'Not required',
};

export const FINAL_STATUS_LABELS: Record<FinalAttendanceStatus, string> = {
  present: 'Present',
  late: 'Late',
  left_early: 'Left early',
  absent: 'Absent',
};

const FINAL_STATUS_MESSAGES: Record<FinalAttendanceStatus, string> = {
  present: 'Your attendance for this session is recorded.',
  late: 'You checked in after the late threshold.',
  left_early: 'Partial attendance. You completed some, but not all, required QR checks.',
  absent: 'No attendance was recorded for this session.',
};

const FINAL_STATUS_TONES: Record<FinalAttendanceStatus, SummaryTone> = {
  present: 'success',
  late: 'warning',
  left_early: 'warning',
  absent: 'error',
};

function locationSatisfied(attendance: MyAttendance): boolean {
  return attendance.verificationPolicy.geofence !== 'required' ||
    attendance.verification.geofenceStatus === 'passed';
}

function isOpen(attendance: MyAttendance): boolean {
  return attendance.sessionState === 'active';
}

function locationStep(attendance: MyAttendance): AttendanceStep | null {
  const { geofence } = attendance.verificationPolicy;
  const title = 'Location verification';
  if (geofence === 'not_required') return null;
  if (geofence === 'waived') {
    return { key: 'location', title, state: 'waived', detail: 'Waived for this session by your lecturer' };
  }
  const evidence = attendance.verification.geofenceStatus;
  if (evidence === 'passed') {
    return { key: 'location', title, state: 'passed', detail: 'Inside the classroom area' };
  }
  if (attendance.verification.attemptStatus === 'failed' && evidence !== null) {
    return { key: 'location', title, state: 'failed', detail: 'Location could not be verified' };
  }
  if (evidence !== null && isOpen(attendance)) {
    return { key: 'location', title, state: 'active', detail: 'Not verified yet. Try again.' };
  }
  if (attendance.canStartCheckIn) {
    return { key: 'location', title, state: 'active', detail: 'Confirm you are in the classroom' };
  }
  return { key: 'location', title, state: 'pending', detail: 'Not started' };
}

function faceStep(attendance: MyAttendance): AttendanceStep | null {
  const title = 'Face verification';
  if (attendance.verificationPolicy.face === 'not_required') return null;
  const { faceStatus, attemptStatus } = attendance.verification;
  if (faceStatus === 'passed') {
    return { key: 'face', title, state: 'passed', detail: 'Identity verified' };
  }
  if (attemptStatus === 'failed' && faceStatus !== null) {
    return { key: 'face', title, state: 'failed', detail: 'Face could not be verified' };
  }
  if (locationSatisfied(attendance) && isOpen(attendance) && attemptStatus !== 'failed' &&
      (attendance.canStartCheckIn || attemptStatus === 'in_progress')) {
    return {
      key: 'face', title, state: 'active',
      detail: faceStatus === null ? 'Ready for face verification' : 'Not verified yet. Try again.',
    };
  }
  return { key: 'face', title, state: 'pending', detail: 'Waiting for location verification' };
}

function qrStep(
  attendance: MyAttendance,
  qrProgress: QrProgress | null,
  qrError: boolean,
): AttendanceStep | null {
  const title = 'QR verification';
  if (!attendance.qrEnabled) return null;
  if (qrError) {
    return { key: 'qr', title, state: 'pending', detail: "Couldn't load QR progress. Pull to refresh." };
  }
  if (!attendance.initialCheckIn) {
    return { key: 'qr', title, state: 'pending', detail: 'Available after you check in' };
  }
  if (!qrProgress) {
    return { key: 'qr', title, state: 'pending', detail: 'Loading QR progress' };
  }

  const { requiredCount, passedCount, activeBatch } = qrProgress;
  const counts = `${passedCount} of ${requiredCount} required checks completed`;
  const scanNow = isOpen(attendance) && activeBatch?.required && !activeBatch.passed;

  if (scanNow) return { key: 'qr', title, state: 'active', detail: `Scan the QR code now · ${counts}` };
  if (requiredCount === 0) {
    return isOpen(attendance)
      ? { key: 'qr', title, state: 'pending', detail: 'No QR checks yet. Waiting for your lecturer.' }
      : { key: 'qr', title, state: 'not_required', detail: 'No QR checks were required' };
  }
  if (passedCount >= requiredCount) return { key: 'qr', title, state: 'passed', detail: counts };
  if (isOpen(attendance)) {
    return { key: 'qr', title, state: 'processing', detail: `${counts} · Waiting for next QR check` };
  }
  return { key: 'qr', title, state: passedCount > 0 ? 'partial' : 'failed', detail: counts };
}

function attendanceStep(attendance: MyAttendance): AttendanceStep {
  const title = 'Attendance';
  const final = attendance.finalAttendance;
  if (final) {
    const label = FINAL_STATUS_LABELS[final.status];
    const source = final.source === 'manual' ? ' · Set by your lecturer' : '';
    const state: StepState = final.status === 'absent' ? 'failed'
      : final.status === 'left_early' ? 'partial' : 'passed';
    return { key: 'attendance', title, state, detail: `${label}${source}` };
  }
  if (attendance.sessionState === 'cancelled') {
    return { key: 'attendance', title, state: 'not_required', detail: 'Session cancelled' };
  }
  if (attendance.initialCheckIn) {
    return {
      key: 'attendance', title, state: 'processing',
      detail: attendance.sessionState === 'closed'
        ? 'Final attendance is being recorded'
        : 'Checked in · Final result when the session closes',
    };
  }
  if (attendance.verification.attemptStatus === 'failed') {
    return { key: 'attendance', title, state: 'failed', detail: 'Check-in not completed' };
  }
  return { key: 'attendance', title, state: 'pending', detail: 'Not checked in yet' };
}

export function buildAttendanceSteps(
  attendance: MyAttendance,
  qrProgress: QrProgress | null,
  qrError = false,
): AttendanceStep[] {
  return [
    locationStep(attendance),
    faceStep(attendance),
    qrStep(attendance, qrProgress, qrError),
    attendanceStep(attendance),
  ].filter((step): step is AttendanceStep => step !== null);
}

// Waived and not-required steps are settled, but only a genuine pass counts
// as "completed" in the progress figure.
export function stepProgress(steps: readonly AttendanceStep[]): { completed: number; total: number } {
  const counted = steps.filter((step) => step.state !== 'not_required' && step.state !== 'waived');
  return {
    completed: counted.filter((step) => step.state === 'passed').length,
    total: counted.length,
  };
}

export function summarizeAttendance(attendance: MyAttendance): AttendanceSummary {
  const final = attendance.finalAttendance;
  if (final) {
    return {
      title: FINAL_STATUS_LABELS[final.status],
      message: final.source === 'manual'
        ? 'Set by your lecturer.'
        : FINAL_STATUS_MESSAGES[final.status],
      tone: FINAL_STATUS_TONES[final.status],
    };
  }
  if (attendance.sessionState === 'cancelled') {
    return {
      title: 'Session cancelled',
      message: attendance.cancellationReason ?? 'No reason was recorded.',
      tone: 'neutral',
    };
  }
  if (attendance.initialCheckIn) {
    return {
      title: attendance.initialCheckIn.status === 'late_checked_in' ? 'Checked in late' : 'Checked in',
      message: 'Final attendance is decided when the session closes.',
      tone: 'info',
    };
  }
  if (attendance.verification.attemptStatus === 'failed') {
    return {
      title: 'Verification failed',
      message: 'Ask your lecturer for help with this session.',
      tone: 'error',
    };
  }
  if (attendance.sessionState === 'closed') {
    return { title: 'Session closed', message: 'Final attendance is being recorded.', tone: 'neutral' };
  }
  if (attendance.sessionState === 'scheduled') {
    return { title: 'Not open yet', message: 'Check-in opens when the session starts.', tone: 'neutral' };
  }
  return {
    title: attendance.verification.attemptStatus ? 'Check-in in progress' : 'Not checked in',
    message: attendance.canStartCheckIn
      ? 'Complete the steps below to check in.'
      : 'Check-in is not available right now.',
    tone: 'info',
  };
}

export type NextAction = 'start_check_in' | 'continue_to_face' | 'none';

// The next thing the student can do, following the step the server says is open.
export function nextCheckInAction(attendance: MyAttendance): NextAction {
  if (!isOpen(attendance) || attendance.initialCheckIn || attendance.finalAttendance) return 'none';
  const { attemptStatus, faceStatus } = attendance.verification;
  if (attemptStatus === 'failed') return 'none';
  if (!attendance.canStartCheckIn && attemptStatus !== 'in_progress') return 'none';
  if (attendance.verificationPolicy.geofence === 'waived') return 'continue_to_face';
  if (locationSatisfied(attendance) && attemptStatus === 'in_progress' &&
      attendance.verificationPolicy.face === 'required' && faceStatus !== 'passed') {
    return 'continue_to_face';
  }
  return 'start_check_in';
}
