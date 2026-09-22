export type LivenessChallenge =
  | 'turn_left'
  | 'turn_right'
  | 'eyes_closed_hold';

/**
 * Camera-independent input consumed by the liveness engine.
 *
 * Nullable measurements represent values the detector could not calculate.
 * The evaluator decides whether a value is required for the active phase.
 */
export type NormalizedFaceObservation = {
  readonly timestampMs: number;
  readonly faceCount: number;
  readonly yawDegrees: number | null;
  readonly leftEyeOpenProbability: number | null;
  readonly rightEyeOpenProbability: number | null;
  readonly faceAreaRatio: number;
  readonly trackingId?: number;
};

export type ChallengeProgress = 'pending' | 'active' | 'completed';

export type ChallengeState = {
  readonly challenge: LivenessChallenge;
  readonly progress: ChallengeProgress;
  readonly startedAtMs: number | null;
  readonly holdStartedAtMs: number | null;
  readonly lastQualifyingAtMs: number | null;
  readonly completedAtMs: number | null;
};

export type FrontalConfirmationState = {
  readonly progress: ChallengeProgress;
  readonly startedAtMs: number | null;
  readonly holdStartedAtMs: number | null;
  readonly lastQualifyingAtMs: number | null;
  readonly completedAtMs: number | null;
};

export type LivenessSessionPhase =
  | 'challenge'
  | 'frontal_confirmation'
  | 'complete';

export type LivenessSessionStatus =
  | 'in_progress'
  | 'passed'
  | 'failed'
  | 'timed_out';

export type LivenessFailureReason =
  | 'no_face'
  | 'multiple_faces'
  | 'face_too_small'
  | 'yaw_unavailable'
  | 'eye_probabilities_unavailable'
  | 'invalid_observation'
  | 'tracking_id_changed';

export type LivenessTimeoutReason =
  | 'challenge_timeout'
  | 'session_timeout';

export type LivenessSessionState = {
  readonly status: LivenessSessionStatus;
  readonly phase: LivenessSessionPhase;
  readonly challenges: readonly [ChallengeState, ChallengeState];
  readonly currentChallengeIndex: 0 | 1 | null;
  readonly frontalConfirmation: FrontalConfirmationState;
  readonly startedAtMs: number;
  readonly phaseStartedAtMs: number;
  readonly completedAtMs: number | null;
  readonly trackingId?: number;
  readonly failureReason: LivenessFailureReason | null;
  readonly timeoutReason: LivenessTimeoutReason | null;
};

export type LivenessEvaluationResult =
  | {
      readonly status: 'continue';
      readonly state: LivenessSessionState;
    }
  | {
      readonly status: 'challenge_completed';
      readonly challenge: LivenessChallenge;
      readonly state: LivenessSessionState;
    }
  | {
      readonly status: 'passed';
      readonly state: LivenessSessionState;
    }
  | {
      readonly status: 'failed';
      readonly reason: LivenessFailureReason;
      readonly state: LivenessSessionState;
    }
  | {
      readonly status: 'timed_out';
      readonly reason: LivenessTimeoutReason;
      readonly state: LivenessSessionState;
    };
