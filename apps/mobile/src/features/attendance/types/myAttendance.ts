import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';

export type InitialCheckIn = {
  readonly status: 'checked_in' | 'late_checked_in';
  readonly checkedInAt: string;
};

export type FinalAttendanceStatus = 'present' | 'late' | 'left_early' | 'absent';

export type StepRequirement = 'required' | 'waived' | 'not_required';

// What the session requires right now. A waived step is a lecturer decision,
// not a pass: the student's own evidence stays in `verification`.
export type VerificationPolicy = {
  readonly geofence: StepRequirement;
  readonly face: StepRequirement;
  readonly geofenceWaivedAt: string | null;
};

export type MyAttendance = {
  readonly sessionId: string;
  readonly courseCode: string;
  readonly courseName: string;
  readonly sessionTitle: string;
  readonly sessionType: string;
  readonly venue: string | null;
  readonly sessionState: 'scheduled' | 'active' | 'closed' | 'cancelled';
  readonly cancellationReason: string | null;
  readonly scheduledStartAt: string;
  readonly scheduledEndAt: string;
  readonly checkInOpensAt: string | null;
  readonly checkInClosesAt: string | null;
  readonly lateAfterAt: string | null;
  readonly requiresFaceVerification: boolean;
  readonly qrEnabled: boolean;
  readonly canStartCheckIn: boolean;
  readonly verification: {
    readonly attemptStatus: 'in_progress' | 'checked_in' | 'failed' | null;
    readonly failureReason: string | null;
    readonly geofenceStatus: string | null;
    readonly faceStatus: string | null;
    readonly livenessPassed: boolean | null;
  };
  readonly initialCheckIn: InitialCheckIn | null;
  readonly verificationPolicy: VerificationPolicy;
  readonly finalAttendance: {
    readonly status: FinalAttendanceStatus;
    readonly source: 'automatic' | 'manual';
    readonly decidedAt: string;
  } | null;
};

export type MyAttendanceResult =
  | { readonly status: 'loaded'; readonly attendance: MyAttendance }
  | { readonly status: CoreApiFailureStatus };

export type CheckInResult =
  | {
      readonly status: 'loaded';
      readonly outcome: 'checked_in' | 'already_checked_in' | 'incomplete';
      readonly initialCheckIn: InitialCheckIn | null;
      readonly missingRequirements: readonly string[];
    }
  | { readonly status: CoreApiFailureStatus; readonly errorCode?: string };

export type StartVerificationResult =
  | { readonly status: 'started'; readonly initialCheckIn: InitialCheckIn | null }
  | { readonly status: 'already_checked_in' }
  | { readonly status: CoreApiFailureStatus; readonly errorCode?: string };
