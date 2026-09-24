import {
  createLivenessSessionState,
  evaluateLivenessObservation,
} from './livenessEvaluator';
import { selectLivenessChallenges } from './livenessChallenge';
import type { LivenessRandomSource } from './livenessChallenge';
import {
  createLivenessEvidence,
  type LivenessEvidence,
} from './livenessEvidence';
import {
  LivenessCaptureSourceError,
  type LivenessCapturedPhoto,
  type ExpoCameraCaptureSource,
} from './expoCameraCaptureSource';
import type {
  LivenessChallenge,
  LivenessEvaluationResult,
  LivenessFailureReason,
  LivenessSessionState,
  LivenessTimeoutReason,
  NormalizedFaceObservation,
} from './livenessTypes';

export type LivenessSessionControllerStatus =
  | 'idle'
  | 'running'
  | 'passed'
  | 'failed'
  | 'timed_out'
  | 'cancelled';

export type LivenessSessionFailure =
  | {
      readonly kind: 'observation';
      readonly reason: LivenessFailureReason;
    }
  | {
      readonly kind: 'capture_source';
      readonly error: LivenessCaptureSourceError;
    };

export type LivenessSessionSnapshot = {
  readonly status: LivenessSessionControllerStatus;
  readonly sessionState: LivenessSessionState | null;
  readonly activeChallenge: LivenessChallenge | null;
  readonly completedChallengeCount: number;
  readonly challengeCount: number;
  readonly failure: LivenessSessionFailure | null;
  readonly timeoutReason: LivenessTimeoutReason | null;
  readonly finalPhoto: { readonly uri: string } | null;
  readonly livenessEvidence: LivenessEvidence | null;
  readonly preparingChallenge: boolean;
};

export type LivenessSessionController = {
  cancel(): void;
  claimFinalPhoto(): LivenessCapturedPhoto | null;
  dispose(): void;
  getSnapshot(): LivenessSessionSnapshot;
  retryCurrentChallenge(): void;
  restart(): void;
  start(): void;
  subscribe(listener: () => void): () => void;
};

type LivenessSessionControllerDependencies = {
  readonly captureSource: ExpoCameraCaptureSource;
  readonly challengePreparationMs?: number;
  readonly now?: () => number;
  readonly random?: LivenessRandomSource;
  readonly wait?: (durationMs: number) => Promise<void>;
};

const INITIAL_SNAPSHOT: LivenessSessionSnapshot = {
  status: 'idle',
  sessionState: null,
  activeChallenge: null,
  completedChallengeCount: 0,
  challengeCount: 0,
  failure: null,
  timeoutReason: null,
  finalPhoto: null,
  livenessEvidence: null,
  preparingChallenge: false,
};

export function createLivenessSessionController({
  captureSource,
  challengePreparationMs = 0,
  now = Date.now,
  random,
  wait = delay,
}: LivenessSessionControllerDependencies): LivenessSessionController {
  let snapshot = INITIAL_SNAPSHOT;
  let runId = 0;
  let workerActive = false;
  let disposed = false;
  let retainedFinalPhoto: LivenessCapturedPhoto | null = null;
  let pendingPhotoCleanup: Promise<void> | null = null;
  let preparedChallengeIndex: number | null = null;
  let frontalConfirmationPrepared = false;
  const listeners = new Set<() => void>();

  const publish = (
    status: LivenessSessionControllerStatus,
    sessionState: LivenessSessionState | null,
    failure: LivenessSessionFailure | null = null,
    timeoutReason: LivenessTimeoutReason | null = null,
    livenessEvidence: LivenessEvidence | null = null,
    preparingChallenge = false,
  ) => {
    snapshot = createSnapshot(
      status,
      sessionState,
      failure,
      timeoutReason,
      status === 'passed' && retainedFinalPhoto
        ? { uri: retainedFinalPhoto.uri }
        : null,
      livenessEvidence,
      preparingChallenge,
    );
    listeners.forEach((listener) => listener());
  };

  const ensureWorker = () => {
    if (workerActive) return;
    void runWorker();
  };

  const beginSession = () => {
    if (disposed) return;
    runId += 1;
    if (retainedFinalPhoto) {
      pendingPhotoCleanup = retainedFinalPhoto.delete();
      retainedFinalPhoto = null;
    }
    const timestampMs = now();
    preparedChallengeIndex = null;
    frontalConfirmationPrepared = false;
    const challenges = selectLivenessChallenges(random);
    const sessionState = createLivenessSessionState(challenges, timestampMs);
    publish('running', sessionState);
    ensureWorker();
  };

  const retryCurrentChallenge = () => {
    if (disposed || snapshot.status === 'running') return;

    const state = snapshot.sessionState;
    const completedChallengeCount =
      state?.challenges.filter(({ progress }) => progress === 'completed')
        .length ?? 0;
    const incompleteChallengeIndex = state?.challenges.findIndex(
      ({ progress }) => progress !== 'completed',
    );
    const challengeIndex =
      incompleteChallengeIndex === 0 || incompleteChallengeIndex === 1
        ? incompleteChallengeIndex
        : null;

    if (
      !state ||
      completedChallengeCount === 0 ||
      challengeIndex === null ||
      snapshot.timeoutReason === 'session_timeout'
    ) {
      beginSession();
      return;
    }

    runId += 1;
    preparedChallengeIndex = null;
    frontalConfirmationPrepared = false;
    const timestampMs = now();
    const challenges = [...state.challenges] as [
      LivenessSessionState['challenges'][0],
      LivenessSessionState['challenges'][1],
    ];
    challenges[challengeIndex] = {
      ...challenges[challengeIndex],
      progress: 'active',
      startedAtMs: timestampMs,
      holdStartedAtMs: null,
      lastQualifyingAtMs: null,
      completedAtMs: null,
    };

    publish('running', {
      ...state,
      status: 'in_progress',
      phase: 'challenge',
      challenges,
      currentChallengeIndex: challengeIndex,
      phaseStartedAtMs: timestampMs,
      completedAtMs: null,
      failureReason: null,
      timeoutReason: null,
    });
    ensureWorker();
  };

  async function runWorker(): Promise<void> {
    workerActive = true;

    try {
      while (snapshot.status === 'running') {
        const observationRunId = runId;
        const cleanup = pendingPhotoCleanup;
        pendingPhotoCleanup = null;

        if (cleanup) {
          try {
            await cleanup;
          } catch (error) {
            if (observationRunId === runId && snapshot.status === 'running') {
              publish('failed', snapshot.sessionState, {
                kind: 'capture_source',
                error: normalizeCaptureSourceError(error),
              });
            }
            continue;
          }

          if (observationRunId !== runId || snapshot.status !== 'running') {
            continue;
          }
        }

        const challengeState = snapshot.sessionState;
        if (
          challengeState?.phase === 'challenge' &&
          challengeState.currentChallengeIndex !== null &&
          preparedChallengeIndex !== challengeState.currentChallengeIndex
        ) {
          if (challengePreparationMs > 0) {
            logLivenessEvent('challenge_preparation_started', {
              challenge:
                challengeState.challenges[
                  challengeState.currentChallengeIndex
                ].challenge,
              durationMs: challengePreparationMs,
            });
            publish('running', challengeState, null, null, null, true);
            await wait(challengePreparationMs);
            if (observationRunId !== runId || snapshot.status !== 'running') {
              continue;
            }
          }

          const preparedAtMs = now();
          const preparedState = markActiveChallengePrepared(
            snapshot.sessionState,
            preparedAtMs,
          );
          preparedChallengeIndex = preparedState.currentChallengeIndex;
          publish('running', preparedState);
        }

        const frontalState = snapshot.sessionState;
        if (
          frontalState?.phase === 'frontal_confirmation' &&
          !frontalConfirmationPrepared
        ) {
          if (challengePreparationMs > 0) {
            logLivenessEvent('frontal_preparation_started', {
              durationMs: challengePreparationMs,
            });
            publish('running', frontalState, null, null, null, true);
            await wait(challengePreparationMs);
            if (observationRunId !== runId || snapshot.status !== 'running') {
              continue;
            }
          }

          const preparedAtMs = now();
          const preparedState = markFrontalConfirmationPrepared(
            snapshot.sessionState,
            preparedAtMs,
          );
          frontalConfirmationPrepared = true;
          publish('running', preparedState);
        }

        let sample;

        try {
          sample = await captureSource.captureSample();
        } catch (error) {
          if (observationRunId !== runId || snapshot.status !== 'running') {
            continue;
          }

          publish('failed', snapshot.sessionState, {
            kind: 'capture_source',
            error: normalizeCaptureSourceError(error),
          });
          continue;
        }

        if (observationRunId !== runId || snapshot.status !== 'running') {
          await deleteStalePhoto(sample.photo, observationRunId, runId, publish, snapshot);
          continue;
        }

        const sessionState = snapshot.sessionState;
        if (!sessionState) {
          publish('failed', null, {
            kind: 'capture_source',
            error: new LivenessCaptureSourceError(
              'capture_failed',
              'The active liveness session state is unavailable.',
            ),
          });
          await deletePhotoOrPublishFailure(sample.photo, publish, snapshot);
          continue;
        }

        const result = evaluateLivenessObservation(
          sessionState,
          sample.observation,
          now(),
        );
        logLivenessEvaluation(sessionState, sample.observation, result);

        if (result.status === 'passed') {
          const livenessEvidence = createLivenessEvidence(result.state);
          if (!livenessEvidence) {
            await deletePhotoOrPublishFailure(
              sample.photo,
              publish,
              snapshot,
              () => observationRunId === runId && snapshot.status === 'running',
            );
            if (observationRunId !== runId || snapshot.status !== 'running') {
              continue;
            }
            publish('failed', result.state, {
              kind: 'capture_source',
              error: new LivenessCaptureSourceError(
                'capture_failed',
                'The passed liveness session could not produce evidence.',
              ),
            });
            continue;
          }
          retainedFinalPhoto = sample.photo;
          publish('passed', result.state, null, null, livenessEvidence);
          continue;
        }

        const deleted = await deletePhotoOrPublishFailure(
          sample.photo,
          publish,
          snapshot,
          () => observationRunId === runId && snapshot.status === 'running',
        );
        if (observationRunId !== runId || snapshot.status !== 'running') {
          continue;
        }
        if (!deleted) continue;

        if (
          result.status === 'continue' ||
          result.status === 'challenge_completed'
        ) {
          publish('running', result.state);
          continue;
        }

        if (result.status === 'timed_out') {
          publish('timed_out', result.state, null, result.reason);
          continue;
        }

        publish('failed', result.state, {
          kind: 'observation',
          reason: result.reason,
        });
      }
    } finally {
      workerActive = false;
      if (snapshot.status === 'running') ensureWorker();
    }
  }

  return {
    cancel() {
      if (snapshot.status !== 'running') return;
      runId += 1;
      publish('cancelled', snapshot.sessionState);
    },
    claimFinalPhoto() {
      const photo = retainedFinalPhoto;
      retainedFinalPhoto = null;
      return photo;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      runId += 1;
      if (snapshot.status === 'running') {
        publish('cancelled', snapshot.sessionState);
      }
      if (retainedFinalPhoto) {
        void retainedFinalPhoto.delete().catch(() => undefined);
        retainedFinalPhoto = null;
      }
      listeners.clear();
    },
    getSnapshot() {
      return snapshot;
    },
    retryCurrentChallenge,
    restart() {
      beginSession();
    },
    start() {
      if (snapshot.status === 'running') return;
      beginSession();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

function createSnapshot(
  status: LivenessSessionControllerStatus,
  sessionState: LivenessSessionState | null,
  failure: LivenessSessionFailure | null,
  timeoutReason: LivenessTimeoutReason | null,
  finalPhoto: { readonly uri: string } | null,
  livenessEvidence: LivenessEvidence | null,
  preparingChallenge = false,
): LivenessSessionSnapshot {
  const activeChallenge =
    status === 'running' &&
    sessionState?.phase === 'challenge' &&
    sessionState.currentChallengeIndex !== null
      ? sessionState.challenges[sessionState.currentChallengeIndex].challenge
      : null;

  return {
    status,
    sessionState,
    activeChallenge,
    completedChallengeCount:
      sessionState?.challenges.filter(
        (challenge) => challenge.progress === 'completed',
      ).length ?? 0,
    challengeCount: sessionState?.challenges.length ?? 0,
    failure,
    timeoutReason,
    finalPhoto,
    livenessEvidence,
    preparingChallenge,
  };
}

function logLivenessEvaluation(
  state: LivenessSessionState,
  observation: NormalizedFaceObservation,
  result: LivenessEvaluationResult,
): void {
  const challenge =
    state.phase === 'challenge' && state.currentChallengeIndex !== null
      ? state.challenges[state.currentChallengeIndex].challenge
      : null;

  logLivenessEvent('observation_evaluated', {
    phase: state.phase,
    challenge,
    faceCount: observation.faceCount,
    yawDegrees: observation.yawDegrees,
    leftEyeOpenProbability: observation.leftEyeOpenProbability,
    rightEyeOpenProbability: observation.rightEyeOpenProbability,
    faceAreaRatio: observation.faceAreaRatio,
    trackingId: observation.trackingId ?? null,
    result: result.status,
    reason: 'reason' in result ? result.reason : null,
  });
}

function logLivenessEvent(
  event: string,
  details: Record<string, unknown>,
): void {
  if (!__DEV__ || process.env.NODE_ENV === 'test') return;
  console.info(`[Liveness] ${event}`, details);
}

function markActiveChallengePrepared(
  state: LivenessSessionState | null,
  timestampMs: number,
): LivenessSessionState {
  if (
    !state ||
    state.phase !== 'challenge' ||
    state.currentChallengeIndex === null
  ) {
    throw new Error('A challenge must be active before preparation completes.');
  }

  const challengeIndex = state.currentChallengeIndex;
  const activeChallenge = {
    ...state.challenges[challengeIndex],
    startedAtMs: timestampMs,
    holdStartedAtMs: null,
    lastQualifyingAtMs: null,
  };

  return {
    ...state,
    phaseStartedAtMs: timestampMs,
    challenges: challengeIndex === 0
      ? [activeChallenge, state.challenges[1]]
      : [state.challenges[0], activeChallenge],
  };
}

function markFrontalConfirmationPrepared(
  state: LivenessSessionState | null,
  timestampMs: number,
): LivenessSessionState {
  if (!state || state.phase !== 'frontal_confirmation') {
    throw new Error('Frontal confirmation must be active before preparation.');
  }

  return {
    ...state,
    phaseStartedAtMs: timestampMs,
    frontalConfirmation: {
      ...state.frontalConfirmation,
      startedAtMs: timestampMs,
      holdStartedAtMs: null,
      lastQualifyingAtMs: null,
    },
  };
}

function delay(durationMs: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, durationMs));
}

async function deletePhotoOrPublishFailure(
  photo: LivenessCapturedPhoto,
  publish: (
    status: LivenessSessionControllerStatus,
    sessionState: LivenessSessionState | null,
    failure?: LivenessSessionFailure | null,
    timeoutReason?: LivenessTimeoutReason | null,
  ) => void,
  snapshot: LivenessSessionSnapshot,
  canPublishFailure: () => boolean = () => true,
): Promise<boolean> {
  try {
    await photo.delete();
    return true;
  } catch (error) {
    if (canPublishFailure()) {
      publish('failed', snapshot.sessionState, {
        kind: 'capture_source',
        error: normalizeCaptureSourceError(error),
      });
    }
    return false;
  }
}

async function deleteStalePhoto(
  photo: LivenessCapturedPhoto,
  observationRunId: number,
  currentRunId: number,
  publish: (
    status: LivenessSessionControllerStatus,
    sessionState: LivenessSessionState | null,
    failure?: LivenessSessionFailure | null,
    timeoutReason?: LivenessTimeoutReason | null,
  ) => void,
  snapshot: LivenessSessionSnapshot,
): Promise<void> {
  try {
    await photo.delete();
  } catch (error) {
    if (observationRunId !== currentRunId && snapshot.status === 'running') {
      publish('failed', snapshot.sessionState, {
        kind: 'capture_source',
        error: normalizeCaptureSourceError(error),
      });
    }
  }
}

function normalizeCaptureSourceError(error: unknown): LivenessCaptureSourceError {
  return error instanceof LivenessCaptureSourceError
    ? error
    : new LivenessCaptureSourceError(
      'capture_failed',
      'The liveness observation source failed.',
      error,
    );
}
