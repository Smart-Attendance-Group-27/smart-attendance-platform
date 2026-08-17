import type { CoreApiFailureStatus } from '../../../services/api/coreApiClient';

export type FaceReadinessStatus =
  | 'not_checked'
  | 'passed'
  | 'failed'
  | 'expired'
  | 'profile_not_enrolled';

export type FaceReadiness = {
  readonly status: FaceReadinessStatus;
  readonly requiresReadinessCheck: boolean;
  readonly checkedAt: string | null;
};

export type FaceReadinessResult =
  | { readonly status: 'loaded'; readonly readiness: FaceReadiness }
  | { readonly status: CoreApiFailureStatus };
