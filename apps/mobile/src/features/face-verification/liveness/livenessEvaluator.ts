import { LIVENESS_THRESHOLDS } from './livenessThresholds';
import type {
  ChallengeState,
  LivenessChallenge,
  LivenessEvaluationResult,
  LivenessFailureReason,
  LivenessSessionState,
  NormalizedFaceObservation,
} from './livenessTypes';

export function createLivenessSessionState(
  challenges: readonly [LivenessChallenge, LivenessChallenge],
  timestampMs: number,
): LivenessSessionState {
  if (!isUsableTimestamp(timestampMs)) {
    throw new RangeError('The liveness session timestamp must be a non-negative finite number.');
  }

  if (challenges[0] === challenges[1]) {
    throw new Error('A liveness session requires two distinct challenges.');
  }

  return {
    status: 'in_progress',
    phase: 'challenge',
    challenges: [
      createChallengeState(challenges[0], 'active', timestampMs),
      createChallengeState(challenges[1], 'pending', null),
    ],
    currentChallengeIndex: 0,
    frontalConfirmation: {
      progress: 'pending',
      startedAtMs: null,
      holdStartedAtMs: null,
      lastQualifyingAtMs: null,
      completedAtMs: null,
    },
    startedAtMs: timestampMs,
    phaseStartedAtMs: timestampMs,
    completedAtMs: null,
    failureReason: null,
    timeoutReason: null,
  };
}

export function evaluateLivenessObservation(
  previousState: LivenessSessionState,
  observation: NormalizedFaceObservation,
  timestampMs: number,
): LivenessEvaluationResult {
  const terminalResult = resultForTerminalState(previousState);

  if (terminalResult) {
    return terminalResult;
  }

  if (
    !isUsableTimestamp(timestampMs) ||
    timestampMs < previousState.startedAtMs ||
    timestampMs < previousState.phaseStartedAtMs
  ) {
    return failure(previousState, 'invalid_observation', timestampMs);
  }

  if (
    timestampMs - previousState.startedAtMs >
    LIVENESS_THRESHOLDS.sessionTimeoutMs
  ) {
    return timedOut(previousState, 'session_timeout', timestampMs);
  }

  if (
    previousState.phase === 'challenge' &&
    timestampMs - previousState.phaseStartedAtMs >
      LIVENESS_THRESHOLDS.challengeTimeoutMs
  ) {
    return timedOut(previousState, 'challenge_timeout', timestampMs);
  }

  const failureReason = validateObservation(previousState, observation);

  if (failureReason) {
    return failure(previousState, failureReason, timestampMs);
  }

  const trackingId = observation.trackingId ?? previousState.trackingId;
  const state = trackingId === undefined
    ? previousState
    : { ...previousState, trackingId };

  if (state.phase === 'challenge' && state.currentChallengeIndex !== null) {
    const challengeState = state.challenges[state.currentChallengeIndex];

    if (
      challengeState.challenge === 'turn_left' ||
      challengeState.challenge === 'turn_right'
    ) {
      return evaluateTurnChallenge(
        state,
        challengeState,
        state.currentChallengeIndex,
        observation,
        timestampMs,
      );
    }

    if (challengeState.challenge === 'eyes_closed_hold') {
      return evaluateEyesClosedChallenge(
        state,
        challengeState,
        state.currentChallengeIndex,
        observation,
        timestampMs,
      );
    }
  }

  if (state.phase === 'frontal_confirmation') {
    return evaluateFrontalConfirmation(state, observation, timestampMs);
  }

  return {
    status: 'continue',
    state,
  };
}

function resultForTerminalState(
  state: LivenessSessionState,
): LivenessEvaluationResult | null {
  if (state.status === 'passed') {
    return { status: 'passed', state };
  }

  if (state.status === 'failed') {
    return {
      status: 'failed',
      reason: state.failureReason ?? 'invalid_observation',
      state,
    };
  }

  if (state.status === 'timed_out') {
    return {
      status: 'timed_out',
      reason: state.timeoutReason ?? 'session_timeout',
      state,
    };
  }

  return null;
}

function evaluateTurnChallenge(
  state: LivenessSessionState,
  challengeState: ChallengeState,
  challengeIndex: 0 | 1,
  observation: NormalizedFaceObservation,
  timestampMs: number,
): LivenessEvaluationResult {
  const yawDegrees = observation.yawDegrees;

  if (!isFiniteNumber(yawDegrees)) {
    return failure(state, 'yaw_unavailable', timestampMs);
  }

  const qualifies = challengeState.challenge === 'turn_left'
    ? yawDegrees >= LIVENESS_THRESHOLDS.leftTurnYawDegrees
    : yawDegrees <= LIVENESS_THRESHOLDS.rightTurnYawDegrees;

  return evaluateHeldChallenge(
    state,
    challengeState,
    challengeIndex,
    observation.timestampMs,
    timestampMs,
    qualifies,
    LIVENESS_THRESHOLDS.turnHoldMs,
  );
}

function evaluateEyesClosedChallenge(
  state: LivenessSessionState,
  challengeState: ChallengeState,
  challengeIndex: 0 | 1,
  observation: NormalizedFaceObservation,
  timestampMs: number,
): LivenessEvaluationResult {
  const leftEye = observation.leftEyeOpenProbability;
  const rightEye = observation.rightEyeOpenProbability;

  if (!isProbability(leftEye) || !isProbability(rightEye)) {
    return failure(state, 'eye_probabilities_unavailable', timestampMs);
  }

  const qualifies =
    leftEye < LIVENESS_THRESHOLDS.eyesClosedMaximumProbability &&
    rightEye < LIVENESS_THRESHOLDS.eyesClosedMaximumProbability;

  return evaluateHeldChallenge(
    state,
    challengeState,
    challengeIndex,
    observation.timestampMs,
    timestampMs,
    qualifies,
    LIVENESS_THRESHOLDS.eyesClosedHoldMs,
  );
}

function evaluateHeldChallenge(
  state: LivenessSessionState,
  challengeState: ChallengeState,
  challengeIndex: 0 | 1,
  observationTimestampMs: number,
  evaluationTimestampMs: number,
  qualifies: boolean,
  requiredHoldMs: number,
): LivenessEvaluationResult {
  if (!qualifies) {
    return {
      status: 'continue',
      state: replaceChallenge(state, challengeIndex, {
        ...challengeState,
        holdStartedAtMs: null,
        lastQualifyingAtMs: null,
      }),
    };
  }

  if (challengeState.holdStartedAtMs === null) {
    return {
      status: 'continue',
      state: replaceChallenge(state, challengeIndex, {
        ...challengeState,
        progress: 'active',
        holdStartedAtMs: observationTimestampMs,
        lastQualifyingAtMs: observationTimestampMs,
      }),
    };
  }

  if (observationTimestampMs < challengeState.holdStartedAtMs) {
    return failure(state, 'invalid_observation', evaluationTimestampMs);
  }

  const nextChallengeState: ChallengeState = {
    ...challengeState,
    lastQualifyingAtMs: observationTimestampMs,
  };

  if (
    observationTimestampMs - challengeState.holdStartedAtMs < requiredHoldMs
  ) {
    return {
      status: 'continue',
      state: replaceChallenge(state, challengeIndex, nextChallengeState),
    };
  }

  const completedChallengeState: ChallengeState = {
    ...nextChallengeState,
    progress: 'completed',
    completedAtMs: observationTimestampMs,
  };

  const completedState = replaceChallenge(
    state,
    challengeIndex,
    completedChallengeState,
  );

  return {
    status: 'challenge_completed',
    challenge: challengeState.challenge,
    state: advanceAfterChallengeCompletion(
      completedState,
      challengeIndex,
      observationTimestampMs,
    ),
  };
}

function evaluateFrontalConfirmation(
  state: LivenessSessionState,
  observation: NormalizedFaceObservation,
  timestampMs: number,
): LivenessEvaluationResult {
  const yawDegrees = observation.yawDegrees;

  if (!isFiniteNumber(yawDegrees)) {
    return failure(state, 'yaw_unavailable', timestampMs);
  }

  const frontalState = state.frontalConfirmation;
  const qualifies =
    Math.abs(yawDegrees) <
    LIVENESS_THRESHOLDS.frontalMaximumAbsoluteYawDegrees;

  if (!qualifies) {
    return {
      status: 'continue',
      state: {
        ...state,
        frontalConfirmation: {
          ...frontalState,
          holdStartedAtMs: null,
          lastQualifyingAtMs: null,
        },
      },
    };
  }

  if (frontalState.holdStartedAtMs === null) {
    return {
      status: 'continue',
      state: {
        ...state,
        frontalConfirmation: {
          ...frontalState,
          progress: 'active',
          holdStartedAtMs: observation.timestampMs,
          lastQualifyingAtMs: observation.timestampMs,
        },
      },
    };
  }

  if (observation.timestampMs < frontalState.holdStartedAtMs) {
    return failure(state, 'invalid_observation', timestampMs);
  }

  if (
    observation.timestampMs - frontalState.holdStartedAtMs <
    LIVENESS_THRESHOLDS.frontalHoldMs
  ) {
    return {
      status: 'continue',
      state: {
        ...state,
        frontalConfirmation: {
          ...frontalState,
          lastQualifyingAtMs: observation.timestampMs,
        },
      },
    };
  }

  const passedState: LivenessSessionState = {
    ...state,
    status: 'passed',
    phase: 'complete',
    completedAtMs: observation.timestampMs,
    frontalConfirmation: {
      ...frontalState,
      progress: 'completed',
      lastQualifyingAtMs: observation.timestampMs,
      completedAtMs: observation.timestampMs,
    },
  };

  return {
    status: 'passed',
    state: passedState,
  };
}

function advanceAfterChallengeCompletion(
  state: LivenessSessionState,
  challengeIndex: 0 | 1,
  timestampMs: number,
): LivenessSessionState {
  if (challengeIndex === 0) {
    const nextChallenge = createChallengeState(
      state.challenges[1].challenge,
      'active',
      timestampMs,
    );

    return {
      ...replaceChallenge(state, 1, nextChallenge),
      currentChallengeIndex: 1,
      phaseStartedAtMs: timestampMs,
    };
  }

  return {
    ...state,
    phase: 'frontal_confirmation',
    currentChallengeIndex: null,
    phaseStartedAtMs: timestampMs,
    frontalConfirmation: {
      progress: 'active',
      startedAtMs: timestampMs,
      holdStartedAtMs: null,
      lastQualifyingAtMs: null,
      completedAtMs: null,
    },
  };
}

function createChallengeState(
  challenge: LivenessChallenge,
  progress: ChallengeState['progress'],
  startedAtMs: number | null,
): ChallengeState {
  return {
    challenge,
    progress,
    startedAtMs,
    holdStartedAtMs: null,
    lastQualifyingAtMs: null,
    completedAtMs: null,
  };
}

function replaceChallenge(
  state: LivenessSessionState,
  challengeIndex: 0 | 1,
  challengeState: ChallengeState,
): LivenessSessionState {
  const challenges: readonly [ChallengeState, ChallengeState] =
    challengeIndex === 0
      ? [challengeState, state.challenges[1]]
      : [state.challenges[0], challengeState];

  return {
    ...state,
    challenges,
  };
}

function validateObservation(
  state: LivenessSessionState,
  observation: NormalizedFaceObservation,
): LivenessFailureReason | null {
  if (
    !isUsableTimestamp(observation.timestampMs) ||
    !Number.isInteger(observation.faceCount) ||
    observation.faceCount < 0 ||
    !isProbability(observation.faceAreaRatio) ||
    (observation.trackingId !== undefined &&
      (!Number.isInteger(observation.trackingId) || observation.trackingId < 0))
  ) {
    return 'invalid_observation';
  }

  if (observation.faceCount === 0) {
    return 'no_face';
  }

  if (observation.faceCount !== 1) {
    return 'multiple_faces';
  }

  if (
    observation.faceAreaRatio < LIVENESS_THRESHOLDS.minimumFaceAreaRatio
  ) {
    return 'face_too_small';
  }

  if (
    state.trackingId !== undefined &&
    observation.trackingId !== undefined &&
    observation.trackingId !== state.trackingId
  ) {
    return 'tracking_id_changed';
  }

  if (state.phase === 'frontal_confirmation') {
    return isFiniteNumber(observation.yawDegrees)
      ? null
      : 'yaw_unavailable';
  }

  if (state.phase !== 'challenge' || state.currentChallengeIndex === null) {
    return null;
  }

  const challenge = state.challenges[state.currentChallengeIndex].challenge;

  if (challenge === 'eyes_closed_hold') {
    return isProbability(observation.leftEyeOpenProbability) &&
      isProbability(observation.rightEyeOpenProbability)
      ? null
      : 'eye_probabilities_unavailable';
  }

  return isFiniteNumber(observation.yawDegrees)
    ? null
    : 'yaw_unavailable';
}

function failure(
  previousState: LivenessSessionState,
  reason: LivenessFailureReason,
  timestampMs: number,
): LivenessEvaluationResult {
  return {
    status: 'failed',
    reason,
    state: {
      ...previousState,
      status: 'failed',
      phase: 'complete',
      currentChallengeIndex: null,
      completedAtMs: timestampMs,
      failureReason: reason,
      timeoutReason: null,
    },
  };
}

function timedOut(
  previousState: LivenessSessionState,
  reason: 'challenge_timeout' | 'session_timeout',
  timestampMs: number,
): LivenessEvaluationResult {
  return {
    status: 'timed_out',
    reason,
    state: {
      ...previousState,
      status: 'timed_out',
      phase: 'complete',
      currentChallengeIndex: null,
      completedAtMs: timestampMs,
      failureReason: null,
      timeoutReason: reason,
    },
  };
}

function isFiniteNumber(value: number | null): value is number {
  return value !== null && Number.isFinite(value);
}

function isProbability(value: number | null): value is number {
  return isFiniteNumber(value) && value >= 0 && value <= 1;
}

function isUsableTimestamp(value: number): boolean {
  return Number.isFinite(value) && value >= 0;
}
