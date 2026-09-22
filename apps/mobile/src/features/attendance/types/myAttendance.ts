import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';

export type InitialCheckIn = {
  readonly status: 'checked_in' | 'late_checked_in';
  readonly checkedInAt: string;
};

export type MyAttendance = {
  readonly sessionId: string;
  readonly courseCode: string;
  readonly courseName: string;
  readonly sessionTitle: string;
  readonly sessionType: string;
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
  readonly finalAttendance: {
    readonly status: 'present' | 'late' | 'absent';
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
