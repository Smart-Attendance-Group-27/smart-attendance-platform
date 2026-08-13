import type { AttendanceOutcome } from './verificationStatus';

export type AttendanceCheckInResult = {
  sessionId: string;
  status: AttendanceOutcome;
  checkInTime: string;
};
