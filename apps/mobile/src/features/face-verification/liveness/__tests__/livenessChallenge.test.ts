import {
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import {
  selectLivenessChallenges,
  SUPPORTED_LIVENESS_CHALLENGES,
  type LivenessRandomSource,
} from '../livenessChallenge';

function sequenceRandom(...values: readonly number[]): LivenessRandomSource {
  const remaining = [...values];

  return jest.fn(() => {
    const value = remaining.shift();

    if (value === undefined) {
      throw new Error('The test random sequence was exhausted.');
    }

    return value;
  });
}

const selectionSamples: [number, number][] = [
  [0, 0],
  [0.2, 0.9],
  [0.5, 0.5],
  [0.999, 0.999],
];

const distinctnessSamples: [number, number][] = [
  [0, 0],
  [0.34, 0.5],
  [0.67, 0.999],
];

describe('selectLivenessChallenges', () => {
  test.each(selectionSamples)('always returns exactly two challenges', (first, second) => {
    const challenges = selectLivenessChallenges(
      sequenceRandom(first, second),
    );

    expect(challenges).toHaveLength(2);
  });

  test.each(distinctnessSamples)('never returns duplicate challenges', (first, second) => {
    const challenges = selectLivenessChallenges(
      sequenceRandom(first, second),
    );

    expect(new Set(challenges).size).toBe(2);
  });

  test('returns only supported production challenges', () => {
    const supported = new Set<string>(SUPPORTED_LIVENESS_CHALLENGES);
    const challenges = selectLivenessChallenges(sequenceRandom(0.8, 0));

    expect(challenges.every((challenge) => supported.has(challenge))).toBe(true);
  });

  test('produces a predictable order with injected randomness', () => {
    const random = sequenceRandom(0.8, 0);

    expect(selectLivenessChallenges(random)).toEqual([
      'eyes_closed_hold',
      'turn_left',
    ]);
    expect(random).toHaveBeenCalledTimes(2);
  });

  test.each([-0.01, 1, Number.NaN, Number.POSITIVE_INFINITY])(
    'rejects an invalid random value of %p',
    (value) => {
      expect(() =>
        selectLivenessChallenges(sequenceRandom(value, 0)),
      ).toThrow(RangeError);
    },
  );
});
