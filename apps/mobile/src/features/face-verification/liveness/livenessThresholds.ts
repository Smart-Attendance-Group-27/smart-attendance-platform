export const LIVENESS_THRESHOLDS = {
  leftTurnYawDegrees: 25,
  rightTurnYawDegrees: -25,
  turnHoldMs: 300,
  eyesClosedMaximumProbability: 0.15,
  eyesClosedHoldMs: 800,
  frontalMaximumAbsoluteYawDegrees: 10,
  frontalHoldMs: 500,
  minimumFaceAreaRatio: 0.15,
  challengeTimeoutMs: 10_000,
  sessionTimeoutMs: 45_000,
} as const;
