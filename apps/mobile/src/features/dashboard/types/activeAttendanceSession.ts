import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';

export type ActiveAttendanceSession = {
  readonly id: string;
  readonly courseCode: string;
  readonly courseName: string;
  readonly sessionTitle: string;
  readonly sessionType: string;
  readonly lecturerNames?: string | null;
  readonly scheduledStartAt: string;
  readonly scheduledEndAt: string;
  readonly checkInOpensAt: string;
  readonly checkInClosesAt: string;
  readonly lateAfterAt: string | null;
  readonly venue: string | null;
  readonly requiresFaceVerification: boolean;
  readonly requiresGeofence: boolean;
  readonly requiresQr: boolean;
};

export type ActiveAttendanceSessionsResult =
  | {
      readonly status: 'loaded';
      readonly sessions: readonly ActiveAttendanceSession[];
    }
  | { readonly status: CoreApiFailureStatus };
