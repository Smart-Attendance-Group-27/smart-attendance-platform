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
  LivenessFailureReason,
  LivenessSessionState,
  LivenessTimeoutReason,
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
};

export type LivenessSessionController = {
  cancel(): void;
  claimFinalPhoto(): LivenessCapturedPhoto | null;
  dispose(): void;
  getSnapshot(): LivenessSessionSnapshot;
  restart(): void;
  start(): void;
  subscribe(listener: () => void): () => void;
};

type LivenessSessionControllerDependencies = {
  readonly captureSource: ExpoCameraCaptureSource;
  readonly now?: () => number;
  readonly random?: LivenessRandomSource;
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
};

export function createLivenessSessionController({
  captureSource,
  now = Date.now,
  random,
}: LivenessSessionControllerDependencies): LivenessSessionController {
  let snapshot = INITIAL_SNAPSHOT;
  let runId = 0;
  let workerActive = false;
  let disposed = false;
  let retainedFinalPhoto: LivenessCapturedPhoto | null = null;
  let pendingPhotoCleanup: Promise<void> | null = null;
  const listeners = new Set<() => void>();

  const publish = (
    status: LivenessSessionControllerStatus,
    sessionState: LivenessSessionState | null,
    failure: LivenessSessionFailure | null = null,
    timeoutReason: LivenessTimeoutReason | null = null,
    livenessEvidence: LivenessEvidence | null = null,
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
    const challenges = selectLivenessChallenges(random);
    const sessionState = createLivenessSessionState(challenges, timestampMs);
    publish('running', sessionState);
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
  };
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
