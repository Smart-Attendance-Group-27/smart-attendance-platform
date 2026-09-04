export type AttendanceVerificationStep =
  | 'location'
  | 'face'
  | 'complete';

export type VerificationStepStatus =
  | 'not_started'
  | 'in_progress'
  | 'passed'
  | 'failed';

/**
 * A FINAL attendance status. The backend decides this once, when the
 * lecturer finalizes the session — never during check-in.
 */
export type AttendanceOutcome =
  | 'present'
  | 'late';

/**
 * What the check-in call can report back.
 *
 * `checked_in` is the normal result: the student passed the start-of-lecture
 * checks and is provisionally present. It is NOT final attendance — the
 * lecturer may still run QR verifications, and the session has to be closed
 * before present/late is decided.
 *
 * `present` / `late` only come back when the session was already finalized
 * before this call, so a stale client reports the real outcome instead of
 * claiming a fresh check-in.
 */
export type CheckInOutcome = 'checked_in' | AttendanceOutcome;
