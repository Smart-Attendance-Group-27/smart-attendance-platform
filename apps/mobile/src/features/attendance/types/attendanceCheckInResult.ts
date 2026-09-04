import type { CheckInOutcome } from './verificationStatus';

export type AttendanceCheckInResult = {
  sessionId: string;
  status: CheckInOutcome;
  /** When initial check-in completed, as reported by the backend. */
  checkInTime: string;
};
