import {
  act,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react-native';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { AppState, type AppStateStatus } from 'react-native';

import { LivenessCamera } from '../components/LivenessCamera';
import {
  LivenessCaptureSourceError,
  type LivenessCapturedPhoto,
} from '../liveness/expoCameraCaptureSource';
import {
  createLivenessEvidence,
  type LivenessEvidence,
} from '../liveness/livenessEvidence';
import { createLivenessSessionState } from '../liveness/livenessEvaluator';
import type {
  LivenessSessionController,
  LivenessSessionFailure,
  LivenessSessionSnapshot,
} from '../liveness/livenessSessionController';
import type { LivenessSessionState } from '../liveness/livenessTypes';

const mockRequestPermission = jest.fn(async () => ({ granted: true }));
let mockPermissionState: { granted: boolean } | null = { granted: true };
let mockCameraMountError:
  | ((event: { message: string }) => void)
  | undefined;
let mockAppStateListener: ((state: AppStateStatus) => void) | undefined;

jest.mock('expo-camera', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text, View } = require('react-native');

  return {
    CameraView: React.forwardRef(
      function MockCameraView(
        {
          facing,
          onCameraReady,
          onMountError,
        }: {
          facing?: string;
          onCameraReady?: () => void;
          onMountError?: (event: { message: string }) => void;
        },
        ref: unknown,
      ) {
        React.useImperativeHandle(ref, () => ({
          takePictureAsync: jest.fn(),
        }));
        React.useEffect(() => {
          onCameraReady?.();
        }, [onCameraReady]);
        React.useEffect(() => {
          mockCameraMountError = onMountError;
          return () => {
            if (mockCameraMountError === onMountError) {
              mockCameraMountError = undefined;
            }
          };
        }, [onMountError]);

        return (
          <View accessibilityLabel="Native liveness camera">
            <Text>Native liveness camera: {facing}</Text>
          </View>
        );
      },
    ),
    useCameraPermissions: () => [
      mockPermissionState,
      mockRequestPermission,
    ],
  };
});

type FakeController = {
  controller: LivenessSessionController;
  finalPhoto: LivenessCapturedPhoto;
  sessionState: LivenessSessionState;
  setSnapshot(snapshot: LivenessSessionSnapshot): void;
};

function createFakeController(): FakeController {
  const sessionState = createLivenessSessionState(
    ['turn_left', 'eyes_closed_hold'],
    1_000,
  );
  let snapshot = createSnapshot('idle', null);
  const listeners = new Set<() => void>();
  const finalPhoto: LivenessCapturedPhoto = {
    uri: 'file:///final-frontal.jpg',
    delete: jest.fn(async () => undefined),
  };
  let unclaimedFinalPhoto: LivenessCapturedPhoto | null = finalPhoto;
  const setSnapshot = (next: LivenessSessionSnapshot) => {
    snapshot = next;
    listeners.forEach((listener) => listener());
  };
  const controller: LivenessSessionController = {
    cancel: jest.fn(() => {
      if (snapshot.status === 'running') {
        setSnapshot(createSnapshot('cancelled', snapshot.sessionState));
      }
    }),
    claimFinalPhoto: jest.fn(() => {
      const photo = unclaimedFinalPhoto;
      unclaimedFinalPhoto = null;
      return photo;
    }),
    dispose: jest.fn(),
    getSnapshot: () => snapshot,
    retryCurrentChallenge: jest.fn(() => {
      setSnapshot(createSnapshot('running', sessionState));
    }),
    restart: jest.fn(() => {
      setSnapshot(createSnapshot('running', sessionState));
    }),
    start: jest.fn(() => {
      setSnapshot(createSnapshot('running', sessionState));
    }),
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };

  return { controller, finalPhoto, sessionState, setSnapshot };
}

function createSnapshot(
  status: LivenessSessionSnapshot['status'],
  sessionState: LivenessSessionState | null,
  failure: LivenessSessionFailure | null = null,
  finalPhoto: { readonly uri: string } | null = null,
  livenessEvidence: LivenessEvidence | null = null,
  timeoutReason: LivenessSessionSnapshot['timeoutReason'] = null,
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
        ({ progress }) => progress === 'completed',
      ).length ?? 0,
    challengeCount: sessionState?.challenges.length ?? 0,
    failure,
    timeoutReason,
    finalPhoto,
    livenessEvidence,
    preparingChallenge: false,
  };
}

function moveToSecondChallenge(
  sessionState: LivenessSessionState,
): LivenessSessionState {
  return {
    ...sessionState,
    challenges: [
      {
        ...sessionState.challenges[0],
        progress: 'completed',
        completedAtMs: 1_300,
      },
      {
        ...sessionState.challenges[1],
        progress: 'active',
        startedAtMs: 1_300,
      },
    ],
    currentChallengeIndex: 1,
    phaseStartedAtMs: 1_300,
  };
}

describe('LivenessCamera', () => {
  beforeEach(() => {
    mockPermissionState = { granted: true };
    mockRequestPermission.mockReset();
    mockRequestPermission.mockResolvedValue({ granted: true });
    mockCameraMountError = undefined;
    mockAppStateListener = undefined;
    jest.spyOn(AppState, 'addEventListener').mockImplementation(
      (_type, listener) => {
        mockAppStateListener = listener;
        return { remove: jest.fn() };
      },
    );
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('starts after the front camera is ready and displays challenge progress', async () => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );

    expect(await screen.findByText('Native liveness camera: front')).toBeTruthy();
    expect(await screen.findByText('Challenge 1 of 2')).toBeTruthy();
    expect(screen.getByText('Turn your head left')).toBeTruthy();
    expect(screen.getByLabelText('Liveness processing').props.accessibilityState)
      .toEqual({ busy: true });
    expect(fake.controller.start).toHaveBeenCalledTimes(1);
  });

  test('shows preparation guidance before challenge capture starts', async () => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    await act(async () => {
      fake.setSnapshot({
        ...createSnapshot('running', fake.sessionState),
        preparingChallenge: true,
      });
    });

    expect(
      screen.getByText('Get into position. Capturing starts in 5 seconds.'),
    ).toBeTruthy();
  });

  test('shows the friendly eyes-closed instruction without renaming the challenge', async () => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    const secondState = moveToSecondChallenge(fake.sessionState);
    await act(async () => {
      fake.setSnapshot(createSnapshot('running', secondState));
    });

    expect(screen.getByText('Challenge 2 of 2')).toBeTruthy();
    expect(
      screen.getByText('Close both eyes and hold'),
    ).toBeTruthy();
    expect(secondState.challenges[1].challenge).toBe('eyes_closed_hold');
  });

  test('plays success feedback as each challenge completes', async () => {
    const fake = createFakeController();
    const hapticFeedback = jest.fn<
      (kind: 'success' | 'error') => Promise<void>
    >(async () => undefined);
    await render(
      <LivenessCamera
        controllerFactory={() => fake.controller}
        hapticFeedback={hapticFeedback}
      />,
    );

    const secondState = moveToSecondChallenge(fake.sessionState);
    await act(async () => {
      fake.setSnapshot(createSnapshot('running', secondState));
    });
    expect(hapticFeedback).toHaveBeenCalledTimes(1);
    expect(hapticFeedback).toHaveBeenLastCalledWith('success');

    const frontalState: LivenessSessionState = {
      ...secondState,
      phase: 'frontal_confirmation',
      challenges: [
        secondState.challenges[0],
        {
          ...secondState.challenges[1],
          progress: 'completed',
          completedAtMs: 1_800,
        },
      ],
      currentChallengeIndex: null,
      phaseStartedAtMs: 1_800,
      frontalConfirmation: {
        ...secondState.frontalConfirmation,
        progress: 'active',
        startedAtMs: 1_800,
      },
    };
    await act(async () => {
      fake.setSnapshot(createSnapshot('running', frontalState));
    });

    expect(hapticFeedback).toHaveBeenCalledTimes(2);
    expect(hapticFeedback).toHaveBeenLastCalledWith('success');
  });

  test.each(['failed', 'timed_out'] as const)(
    'plays error feedback once when the session becomes %s',
    async (status) => {
      const fake = createFakeController();
      const hapticFeedback = jest.fn<
        (kind: 'success' | 'error') => Promise<void>
      >(async () => undefined);
      await render(
        <LivenessCamera
          controllerFactory={() => fake.controller}
          hapticFeedback={hapticFeedback}
        />,
      );

      const terminalSnapshot = createSnapshot(
        status,
        fake.sessionState,
        status === 'failed'
          ? { kind: 'observation', reason: 'no_face' }
          : null,
        null,
        null,
        status === 'timed_out' ? 'challenge_timeout' : null,
      );
      await act(async () => {
        fake.setSnapshot(terminalSnapshot);
      });
      await act(async () => {
        fake.setSnapshot({ ...terminalSnapshot });
      });

      expect(hapticFeedback).toHaveBeenCalledTimes(1);
      expect(hapticFeedback).toHaveBeenCalledWith('error');
    },
  );

  test('shows a recoverable local failure and retries through the controller', async () => {
    const fake = createFakeController();
    const onSuccess = jest.fn();
    const screen = await render(
      <LivenessCamera
        controllerFactory={() => fake.controller}
        onSuccess={onSuccess}
      />,
    );
    await screen.findByText('Turn your head left');

    await act(async () => {
      fake.setSnapshot(createSnapshot('failed', fake.sessionState, {
        kind: 'observation',
        reason: 'no_face',
      }));
    });

    expect(screen.getByText('Liveness check could not continue')).toBeTruthy();
    expect(
      screen.getByText(
        'Keep your face fully visible inside the guide and try again.',
      ),
    ).toBeTruthy();
    expect(onSuccess).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByRole('button', { name: 'Try Again' }));
    expect(fake.controller.retryCurrentChallenge).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Turn your head left')).toBeTruthy();
  });

  test('displays success and reports the completed local session once', async () => {
    const fake = createFakeController();
    const onSuccess = jest.fn();
    const screen = await render(
      <LivenessCamera
        controllerFactory={() => fake.controller}
        onSuccess={onSuccess}
      />,
    );
    await screen.findByText('Turn your head left');
    const passedState: LivenessSessionState = {
      ...fake.sessionState,
      status: 'passed',
      phase: 'complete',
      currentChallengeIndex: null,
      completedAtMs: 2_500,
    };
    const livenessEvidence = createLivenessEvidence(passedState);
    if (!livenessEvidence) throw new Error('Expected passed evidence.');

    await act(async () => {
      fake.setSnapshot(createSnapshot(
        'passed',
        passedState,
        null,
        { uri: fake.finalPhoto.uri },
        livenessEvidence,
      ));
    });

    expect(screen.getByText('Liveness check passed')).toBeTruthy();
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(onSuccess).toHaveBeenCalledWith({
      photo: fake.finalPhoto,
      livenessEvidence,
    });
  });

  test('cancels through the controller and invokes the optional callback', async () => {
    const fake = createFakeController();
    const onCancel = jest.fn();
    const screen = await render(
      <LivenessCamera
        controllerFactory={() => fake.controller}
        onCancel={onCancel}
      />,
    );
    await screen.findByText('Turn your head left');

    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));

    expect(fake.controller.cancel).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Liveness check cancelled')).toBeTruthy();
  });

  test('keeps capture local when camera permission is denied', async () => {
    mockPermissionState = { granted: false };
    mockRequestPermission.mockResolvedValueOnce({ granted: false });
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );

    expect(screen.getByText('Camera permission required')).toBeTruthy();
    expect(screen.queryByLabelText('Native liveness camera')).toBeNull();

    await fireEvent.press(
      screen.getByRole('button', { name: 'Allow Camera Access' }),
    );

    expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    expect(fake.controller.start).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Native liveness camera')).toBeNull();
  });

  test('recovers from a native camera mount error by remounting and restarting', async () => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    await act(async () => {
      mockCameraMountError?.({ message: 'Front camera unavailable.' });
    });

    expect(screen.getByText('Camera could not start')).toBeTruthy();
    expect(screen.getByText('Front camera unavailable.')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Try Again' }));

    expect(fake.controller.restart).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Turn your head left')).toBeTruthy();
  });

  test.each([
    {
      code: 'camera_unavailable' as const,
      message: 'Wait for the front camera to become ready, then try again.',
    },
    {
      code: 'capture_failed' as const,
      message: 'The camera could not capture an image. Please try again.',
    },
    {
      code: 'detection_failed' as const,
      message: 'Your face could not be analyzed locally. Please try again.',
    },
  ])('shows a recoverable $code source error', async ({ code, message }) => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    await act(async () => {
      fake.setSnapshot(createSnapshot('failed', fake.sessionState, {
        kind: 'capture_source',
        error: new LivenessCaptureSourceError(code, 'local failure'),
      }));
    });

    expect(screen.getByText(message)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try Again' })).toBeTruthy();
  });

  test.each([
    {
      reason: 'multiple_faces' as const,
      message: 'Make sure only one person is visible and try again.',
    },
    {
      reason: 'face_too_small' as const,
      message: 'Move closer to the camera and try again.',
    },
    {
      reason: 'yaw_unavailable' as const,
      message: 'Keep your full face visible and try the movement again.',
    },
    {
      reason: 'eye_probabilities_unavailable' as const,
      message: 'Keep both eyes clearly visible and try again.',
    },
    {
      reason: 'invalid_observation' as const,
      message: 'The camera reading was invalid. Please try again.',
    },
  ])('shows local guidance for $reason', async ({ reason, message }) => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    await act(async () => {
      fake.setSnapshot(createSnapshot('failed', fake.sessionState, {
        kind: 'observation',
        reason,
      }));
    });

    expect(screen.getByText(message)).toBeTruthy();
  });

  test.each(['challenge_timeout', 'session_timeout'] as const)(
    'shows a recoverable message for %s',
    async (timeoutReason) => {
      const fake = createFakeController();
      const screen = await render(
        <LivenessCamera controllerFactory={() => fake.controller} />,
      );
      await screen.findByText('Turn your head left');

      await act(async () => {
        fake.setSnapshot(createSnapshot(
          'timed_out',
          fake.sessionState,
          null,
          null,
          null,
          timeoutReason,
        ));
      });

      expect(screen.getByText('Liveness check timed out')).toBeTruthy();
      expect(screen.getByRole('button', { name: 'Try Again' })).toBeTruthy();
    },
  );

  test('cancels the local session when the app leaves the foreground', async () => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    await act(async () => {
      mockAppStateListener?.('background');
    });

    expect(fake.controller.cancel).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Liveness check cancelled')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Try Again' })).toBeTruthy();
  });

  test('disposes the controller when the component unmounts', async () => {
    const fake = createFakeController();
    const screen = await render(
      <LivenessCamera controllerFactory={() => fake.controller} />,
    );
    await screen.findByText('Turn your head left');

    await screen.unmount();

    expect(fake.controller.dispose).toHaveBeenCalledTimes(1);
  });
});
