export type AttendanceVerificationStep =
  | 'location'
  | 'face'
  | 'complete';

export type VerificationStepStatus =
  | 'not_started'
  | 'in_progress'
  | 'passed'
  | 'failed';

export type AttendanceOutcome =
  | 'present'
  | 'late';
