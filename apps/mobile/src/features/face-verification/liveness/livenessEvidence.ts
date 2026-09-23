import type {
  LivenessChallenge,
  LivenessSessionState,
} from './livenessTypes';

export const LIVENESS_ENGINE = 'uniattend-mobile-liveness' as const;

export type LivenessEvidence = {
  readonly version: 1;
  readonly method: 'mlkit_challenge';
  readonly passed: true;
  readonly challenges: readonly LivenessChallenge[];
  readonly startedAt: string;
  readonly completedAt: string;
  readonly engine: typeof LIVENESS_ENGINE;
};

export function createLivenessEvidence(
  sessionState: LivenessSessionState,
): LivenessEvidence | null {
  if (
    sessionState.status !== 'passed' ||
    sessionState.phase !== 'complete' ||
    sessionState.completedAtMs === null
  ) {
    return null;
  }

  if (
    !isValidDateTimestamp(sessionState.startedAtMs) ||
    !isValidDateTimestamp(sessionState.completedAtMs) ||
    sessionState.startedAtMs > sessionState.completedAtMs
  ) {
    throw new RangeError('A passed liveness session has invalid timestamps.');
  }

  return {
    version: 1,
    method: 'mlkit_challenge',
    passed: true,
    challenges: sessionState.challenges.map(({ challenge }) => challenge),
    startedAt: new Date(sessionState.startedAtMs).toISOString(),
    completedAt: new Date(sessionState.completedAtMs).toISOString(),
    engine: LIVENESS_ENGINE,
  };
}

function isValidDateTimestamp(value: number): boolean {
  return Number.isFinite(value) &&
    value >= 0 &&
    value <= 8_640_000_000_000_000;
}
