import { describe, expect, test } from '@jest/globals';

import { createLivenessEvidence } from '../livenessEvidence';
import { createLivenessSessionState } from '../livenessEvaluator';
import type { LivenessSessionState } from '../livenessTypes';

function passedSession(): LivenessSessionState {
  const session = createLivenessSessionState(
    ['turn_left', 'eyes_closed_hold'],
    1_000,
  );

  return {
    ...session,
    status: 'passed',
    phase: 'complete',
    currentChallengeIndex: null,
    completedAtMs: 9_000,
  };
}

describe('createLivenessEvidence', () => {
  test('produces the frozen evidence contract from a successful session', () => {
    expect(createLivenessEvidence(passedSession())).toEqual({
      version: 1,
      method: 'mlkit_challenge',
      passed: true,
      challenges: ['turn_left', 'eyes_closed_hold'],
      startedAt: '1970-01-01T00:00:01.000Z',
      completedAt: '1970-01-01T00:00:09.000Z',
      engine: 'uniattend-mobile-liveness',
    });
  });

  test('preserves the exact selected challenge vocabulary and order', () => {
    const session = passedSession();

    expect(createLivenessEvidence(session)?.challenges).toEqual([
      'turn_left',
      'eyes_closed_hold',
    ]);
    expect(createLivenessEvidence(session)?.challenges).not.toContain('blink');
  });

  test.each(['in_progress', 'failed', 'timed_out'] as const)(
    'does not produce passed evidence for a %s session',
    (status) => {
      const session: LivenessSessionState = {
        ...passedSession(),
        status,
        phase: status === 'in_progress' ? 'challenge' : 'complete',
      };

      expect(createLivenessEvidence(session)).toBeNull();
    },
  );

  test('rejects invalid timestamp ordering instead of fabricating evidence', () => {
    const session: LivenessSessionState = {
      ...passedSession(),
      startedAtMs: 10_000,
      completedAtMs: 9_000,
    };

    expect(() => createLivenessEvidence(session)).toThrow(RangeError);
  });
});
