import {
  describe,
  expect,
  test,
} from '@jest/globals';

import {
  createLivenessSessionState,
  evaluateLivenessObservation,
} from '../livenessEvaluator';
import type {
  LivenessChallenge,
  LivenessSessionState,
  NormalizedFaceObservation,
} from '../livenessTypes';

const EVALUATED_AT_MS = 1_100;

function createSessionState(
  options: {
    readonly challenge?: LivenessChallenge;
    readonly trackingId?: number;
  } = {},
): LivenessSessionState {
  const firstChallenge = options.challenge ?? 'turn_left';
  const secondChallenge = firstChallenge === 'turn_right'
    ? 'turn_left'
    : 'turn_right';
  const state = createLivenessSessionState(
    [firstChallenge, secondChallenge],
    1_000,
  );

  return options.trackingId === undefined
    ? state
    : { ...state, trackingId: options.trackingId };
}

function createObservation(
  overrides: Partial<NormalizedFaceObservation> = {},
): NormalizedFaceObservation {
  return {
    timestampMs: EVALUATED_AT_MS,
    faceCount: 1,
    yawDegrees: 30,
    leftEyeOpenProbability: 0.99,
    rightEyeOpenProbability: 0.99,
    faceAreaRatio: 0.2,
    ...overrides,
  };
}

function advanceToFrontalConfirmation(): LivenessSessionState {
  const initial = createLivenessSessionState(
    ['turn_left', 'turn_right'],
    1_000,
  );
  const leftStarted = evaluateLivenessObservation(
    initial,
    createObservation({ timestampMs: 1_100, yawDegrees: 30 }),
    1_100,
  );
  const leftCompleted = evaluateLivenessObservation(
    leftStarted.state,
    createObservation({ timestampMs: 1_400, yawDegrees: 30 }),
    1_400,
  );
  const rightStarted = evaluateLivenessObservation(
    leftCompleted.state,
    createObservation({ timestampMs: 1_500, yawDegrees: -30 }),
    1_500,
  );

  return evaluateLivenessObservation(
    rightStarted.state,
    createObservation({ timestampMs: 1_800, yawDegrees: -30 }),
    1_800,
  ).state;
}

describe('evaluateLivenessObservation common validation', () => {
  test('fails when no face is detected', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ faceCount: 0 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('failed');
    expect(result.state.failureReason).toBe('no_face');
  });

  test('fails when multiple faces are detected', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ faceCount: 2 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('failed');
    expect(result.state.failureReason).toBe('multiple_faces');
  });

  test('fails when the face area is below fifteen percent', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ faceAreaRatio: 0.149 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('failed');
    expect(result.state.failureReason).toBe('face_too_small');
  });

  test('accepts one valid face at the minimum area', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ faceAreaRatio: 0.15 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.failureReason).toBeNull();
    expect(result.state.challenges[0].holdStartedAtMs).toBe(EVALUATED_AT_MS);
  });

  test('continues when the tracking ID remains the same', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ trackingId: 42 }),
      createObservation({ trackingId: 42 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.trackingId).toBe(42);
  });

  test('fails when an established tracking ID changes', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ trackingId: 42 }),
      createObservation({ trackingId: 84 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('failed');
    expect(result.state.failureReason).toBe('tracking_id_changed');
  });

  test('continues when tracking IDs are absent', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation(),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.trackingId).toBeUndefined();
  });

  test('does not fail when a later observation omits a tracking ID', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ trackingId: 42 }),
      createObservation(),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.trackingId).toBe(42);
  });

  test('records the first available tracking ID', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ trackingId: 42 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.trackingId).toBe(42);
  });

  test('requires usable yaw for a turn challenge', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ yawDegrees: null }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('failed');
    expect(result.state.failureReason).toBe('yaw_unavailable');
  });

  test('requires both eye probabilities for eyes-closed hold', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({ rightEyeOpenProbability: null }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('failed');
    expect(result.state.failureReason).toBe(
      'eye_probabilities_unavailable',
    );
  });
});

describe('evaluateLivenessObservation turn challenges', () => {
  test('completes a left turn held across qualifying observations', () => {
    const started = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ timestampMs: 1_100, yawDegrees: 25 }),
      1_100,
    );
    const completed = evaluateLivenessObservation(
      started.state,
      createObservation({ timestampMs: 1_400, yawDegrees: 31 }),
      1_400,
    );

    expect(completed.status).toBe('challenge_completed');
    expect(completed.state.challenges[0].progress).toBe('completed');
  });

  test('completes a right turn held across qualifying observations', () => {
    const started = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_right' }),
      createObservation({ timestampMs: 1_100, yawDegrees: -25 }),
      1_100,
    );
    const completed = evaluateLivenessObservation(
      started.state,
      createObservation({ timestampMs: 1_401, yawDegrees: -30 }),
      1_401,
    );

    expect(completed.status).toBe('challenge_completed');
    expect(completed.state.challenges[0].progress).toBe('completed');
  });

  test('+24 degrees does not satisfy a left turn', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ yawDegrees: 24 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.challenges[0].holdStartedAtMs).toBeNull();
  });

  test('-24 degrees does not satisfy a right turn', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_right' }),
      createObservation({ yawDegrees: -24 }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.challenges[0].holdStartedAtMs).toBeNull();
  });

  test('turning in the wrong direction does not start the hold', () => {
    const leftResult = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ yawDegrees: -40 }),
      EVALUATED_AT_MS,
    );
    const rightResult = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_right' }),
      createObservation({ yawDegrees: 40 }),
      EVALUATED_AT_MS,
    );

    expect(leftResult.state.challenges[0].holdStartedAtMs).toBeNull();
    expect(rightResult.state.challenges[0].holdStartedAtMs).toBeNull();
  });

  test('one qualifying observation does not immediately pass', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ timestampMs: 1_100, yawDegrees: 35 }),
      1_100,
    );

    expect(result.status).toBe('continue');
    expect(result.state.challenges[0].holdStartedAtMs).toBe(1_100);
  });

  test('qualifying observations separated by exactly 300 ms pass', () => {
    const started = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ timestampMs: 2_000, yawDegrees: 30 }),
      2_000,
    );
    const completed = evaluateLivenessObservation(
      started.state,
      createObservation({ timestampMs: 2_300, yawDegrees: 30 }),
      2_300,
    );

    expect(completed.status).toBe('challenge_completed');
  });

  test('an interrupted pose resets the hold', () => {
    const firstHold = evaluateLivenessObservation(
      createSessionState({ challenge: 'turn_left' }),
      createObservation({ timestampMs: 1_100, yawDegrees: 30 }),
      1_100,
    );
    const interrupted = evaluateLivenessObservation(
      firstHold.state,
      createObservation({ timestampMs: 1_250, yawDegrees: 0 }),
      1_250,
    );
    const restarted = evaluateLivenessObservation(
      interrupted.state,
      createObservation({ timestampMs: 1_500, yawDegrees: 30 }),
      1_500,
    );

    expect(interrupted.state.challenges[0].holdStartedAtMs).toBeNull();
    expect(restarted.status).toBe('continue');
    expect(restarted.state.challenges[0].holdStartedAtMs).toBe(1_500);
  });
});

describe('evaluateLivenessObservation eyes-closed hold', () => {
  test('completes a sustained eyes-closed hold', () => {
    const started = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({
        timestampMs: 2_000,
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.01,
      }),
      2_000,
    );
    const completed = evaluateLivenessObservation(
      started.state,
      createObservation({
        timestampMs: 2_850,
        leftEyeOpenProbability: 0.07,
        rightEyeOpenProbability: 0.03,
      }),
      2_850,
    );

    expect(completed.status).toBe('challenge_completed');
    expect(completed.state.challenges[0].completedAtMs).toBe(2_850);
  });

  test('does not start when only one eye is closed', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.95,
      }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.challenges[0].holdStartedAtMs).toBeNull();
  });

  test('does not start when either eye equals the 0.15 boundary', () => {
    const result = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({
        leftEyeOpenProbability: 0.14,
        rightEyeOpenProbability: 0.15,
      }),
      EVALUATED_AT_MS,
    );

    expect(result.status).toBe('continue');
    expect(result.state.challenges[0].holdStartedAtMs).toBeNull();
  });

  test('does not complete when the closed interval is less than 800 ms', () => {
    const started = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({
        timestampMs: 2_000,
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.02,
      }),
      2_000,
    );
    const result = evaluateLivenessObservation(
      started.state,
      createObservation({
        timestampMs: 2_799,
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.02,
      }),
      2_799,
    );

    expect(result.status).toBe('continue');
    expect(result.state.challenges[0].completedAtMs).toBeNull();
  });

  test('completes when closed observations span exactly 800 ms', () => {
    const started = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({
        timestampMs: 2_000,
        leftEyeOpenProbability: 0.05,
        rightEyeOpenProbability: 0.05,
      }),
      2_000,
    );
    const completed = evaluateLivenessObservation(
      started.state,
      createObservation({
        timestampMs: 2_800,
        leftEyeOpenProbability: 0.05,
        rightEyeOpenProbability: 0.05,
      }),
      2_800,
    );

    expect(completed.status).toBe('challenge_completed');
  });

  test('reopening either eye resets the hold', () => {
    const firstHold = evaluateLivenessObservation(
      createSessionState({ challenge: 'eyes_closed_hold' }),
      createObservation({
        timestampMs: 2_000,
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.02,
      }),
      2_000,
    );
    const reopened = evaluateLivenessObservation(
      firstHold.state,
      createObservation({
        timestampMs: 2_500,
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.9,
      }),
      2_500,
    );
    const restarted = evaluateLivenessObservation(
      reopened.state,
      createObservation({
        timestampMs: 2_900,
        leftEyeOpenProbability: 0.02,
        rightEyeOpenProbability: 0.02,
      }),
      2_900,
    );

    expect(reopened.state.challenges[0].holdStartedAtMs).toBeNull();
    expect(restarted.status).toBe('continue');
    expect(restarted.state.challenges[0].holdStartedAtMs).toBe(2_900);
  });
});

describe('evaluateLivenessObservation session flow', () => {
  test('completing challenge one advances to challenge two', () => {
    const initial = createLivenessSessionState(
      ['turn_left', 'turn_right'],
      1_000,
    );
    const started = evaluateLivenessObservation(
      initial,
      createObservation({ timestampMs: 1_100, yawDegrees: 30 }),
      1_100,
    );
    const completed = evaluateLivenessObservation(
      started.state,
      createObservation({ timestampMs: 1_400, yawDegrees: 30 }),
      1_400,
    );

    expect(completed.status).toBe('challenge_completed');
    expect(completed.state.currentChallengeIndex).toBe(1);
    expect(completed.state.challenges[0].progress).toBe('completed');
    expect(completed.state.challenges[1].progress).toBe('active');
  });

  test('completing challenge two advances to frontal confirmation', () => {
    const state = advanceToFrontalConfirmation();

    expect(state.phase).toBe('frontal_confirmation');
    expect(state.currentChallengeIndex).toBeNull();
    expect(state.challenges[1].progress).toBe('completed');
    expect(state.frontalConfirmation.progress).toBe('active');
  });

  test('frontal yaw at or outside ten degrees does not pass', () => {
    const state = advanceToFrontalConfirmation();
    const first = evaluateLivenessObservation(
      state,
      createObservation({ timestampMs: 2_000, yawDegrees: 3 }),
      2_000,
    );
    const interrupted = evaluateLivenessObservation(
      first.state,
      createObservation({ timestampMs: 2_600, yawDegrees: 10 }),
      2_600,
    );

    expect(interrupted.status).toBe('continue');
    expect(interrupted.state.status).toBe('in_progress');
    expect(
      interrupted.state.frontalConfirmation.holdStartedAtMs,
    ).toBeNull();
  });

  test('a frontal pose spanning exactly 500 ms passes', () => {
    const state = advanceToFrontalConfirmation();
    const started = evaluateLivenessObservation(
      state,
      createObservation({ timestampMs: 2_000, yawDegrees: -9.9 }),
      2_000,
    );
    const passed = evaluateLivenessObservation(
      started.state,
      createObservation({ timestampMs: 2_500, yawDegrees: 9.9 }),
      2_500,
    );

    expect(passed.status).toBe('passed');
    expect(passed.state.status).toBe('passed');
    expect(passed.state.frontalConfirmation.progress).toBe('completed');
  });

  test('completes an entire two-challenge liveness session', () => {
    const frontal = advanceToFrontalConfirmation();
    const frontalStarted = evaluateLivenessObservation(
      frontal,
      createObservation({ timestampMs: 2_000, yawDegrees: 0 }),
      2_000,
    );
    const passed = evaluateLivenessObservation(
      frontalStarted.state,
      createObservation({ timestampMs: 2_600, yawDegrees: 2 }),
      2_600,
    );

    expect(passed).toMatchObject({
      status: 'passed',
      state: {
        status: 'passed',
        phase: 'complete',
        currentChallengeIndex: null,
        completedAtMs: 2_600,
      },
    });
    expect(passed.state.challenges.every(
      (challenge) => challenge.progress === 'completed',
    )).toBe(true);
  });
});

describe('evaluateLivenessObservation timeouts', () => {
  test('continues while the active challenge is under six seconds', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ timestampMs: 6_999, yawDegrees: 0 }),
      6_999,
    );

    expect(result.status).toBe('continue');
    expect(result.state.timeoutReason).toBeNull();
  });

  test('times out when the active challenge exceeds six seconds', () => {
    const result = evaluateLivenessObservation(
      createSessionState(),
      createObservation({ timestampMs: 7_001, yawDegrees: 30 }),
      7_001,
    );

    expect(result.status).toBe('timed_out');
    expect(result.state.status).toBe('timed_out');
    expect(result.state.timeoutReason).toBe('challenge_timeout');
  });

  test('continues while the overall session is under twenty-five seconds', () => {
    const result = evaluateLivenessObservation(
      advanceToFrontalConfirmation(),
      createObservation({ timestampMs: 25_999, yawDegrees: 0 }),
      25_999,
    );

    expect(result.status).toBe('continue');
    expect(result.state.timeoutReason).toBeNull();
  });

  test('times out when the overall session exceeds twenty-five seconds', () => {
    const result = evaluateLivenessObservation(
      advanceToFrontalConfirmation(),
      createObservation({ timestampMs: 26_001, yawDegrees: 0 }),
      26_001,
    );

    expect(result.status).toBe('timed_out');
    expect(result.state.timeoutReason).toBe('session_timeout');
  });

  test('an overall timeout takes precedence over a passing frontal pose', () => {
    const frontalStarted = evaluateLivenessObservation(
      advanceToFrontalConfirmation(),
      createObservation({ timestampMs: 25_400, yawDegrees: 0 }),
      25_400,
    );
    const result = evaluateLivenessObservation(
      frontalStarted.state,
      createObservation({ timestampMs: 26_001, yawDegrees: 0 }),
      26_001,
    );

    expect(result.status).toBe('timed_out');
    expect(result.state.status).not.toBe('passed');
    expect(result.state.timeoutReason).toBe('session_timeout');
  });
});
