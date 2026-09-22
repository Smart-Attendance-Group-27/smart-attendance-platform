import type { LivenessChallenge } from './livenessTypes';

export const SUPPORTED_LIVENESS_CHALLENGES = [
  'turn_left',
  'turn_right',
  'eyes_closed_hold',
] as const satisfies readonly LivenessChallenge[];

export type LivenessRandomSource = () => number;

export function selectLivenessChallenges(
  random: LivenessRandomSource = Math.random,
): readonly [LivenessChallenge, LivenessChallenge] {
  const available: LivenessChallenge[] = [
    ...SUPPORTED_LIVENESS_CHALLENGES,
  ];
  const first = available.splice(randomIndex(random, available.length), 1)[0];
  const second = available[randomIndex(random, available.length)];

  return [first, second];
}

function randomIndex(random: LivenessRandomSource, length: number): number {
  const value = random();

  if (!Number.isFinite(value) || value < 0 || value >= 1) {
    throw new RangeError('Liveness randomness must be between 0 inclusive and 1 exclusive.');
  }

  return Math.floor(value * length);
}
