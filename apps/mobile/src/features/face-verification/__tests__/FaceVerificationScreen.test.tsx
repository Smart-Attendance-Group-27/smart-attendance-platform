import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import {
  act,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react-native';

import type { LivenessCameraResult } from '../components/LivenessCamera';
import { FaceVerificationScreen } from '../screens/FaceVerificationScreen';
import type { FaceVerificationService } from '../services/faceVerificationService';
import { MockFaceVerificationService } from '../services/mockFaceVerificationService';
import type { FaceVerificationResult } from '../types/faceVerification';

const mockRequestCameraPermission = jest.fn<
  () => Promise<{ granted: boolean }>
>();
const mockTakePictureAsync = jest.fn<
  () => Promise<{ uri: string }>
>();
let mockPermissionState: { granted: boolean } | null = { granted: true };
let mockLivenessOnSuccess:
  | ((result: LivenessCameraResult) => void)
  | undefined;
let mockLivenessSessionStarts = 0;
let mockLocalLivenessOutcome = 'Liveness running';

jest.mock('expo-camera', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text, View } = require('react-native');

  return {
    CameraView: React.forwardRef(
      function MockCameraView(
        {
          onCameraReady,
        }: {
          onCameraReady?: () => void;
        },
        ref: unknown,
      ) {
        React.useImperativeHandle(ref, () => ({
          takePictureAsync: mockTakePictureAsync,
        }));
        React.useEffect(() => {
          onCameraReady?.();
        }, [onCameraReady]);

        return (
          <View accessibilityLabel="Native front camera">
            <Text>Native front camera</Text>
          </View>
        );
      },
    ),
    useCameraPermissions: () => [
      mockPermissionState,
      mockRequestCameraPermission,
    ],
  };
});

jest.mock('../components/LivenessCamera', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text, View } = require('react-native');

  return {
    LivenessCamera: ({
      onSuccess,
    }: {
      onSuccess?: (result: LivenessCameraResult) => void;
    }) => {
      mockLivenessOnSuccess = onSuccess;
      React.useEffect(() => {
        mockLivenessSessionStarts += 1;
      }, []);

      return (
        <View accessibilityLabel="Local liveness camera">
          <Text>Local liveness camera</Text>
          <Text>{mockLocalLivenessOutcome}</Text>
        </View>
      );
    },
  };
});

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const failureOutcomes = [
  {
    result: { status: 'face_not_detected' } as const,
    title: 'Face not detected',
    message:
      'Make sure your face is clearly visible inside the frame and try again.',
  },
  {
    result: { status: 'multiple_faces' } as const,
    title: 'Multiple faces detected',
    message: 'Make sure only your face is visible in the camera frame.',
  },
  {
    result: { status: 'liveness_failure' } as const,
    title: 'Verification could not confirm liveness',
    message: 'Keep your face visible and steady, then try again.',
  },
  {
    result: { status: 'verification_failure' } as const,
    title: 'Face verification failed',
    message: "We couldn't verify your face. Please try again.",
  },
];

function createSuccessfulLivenessResult(
  uri = 'file:///final-liveness-photo.jpg',
): LivenessCameraResult & {
  readonly photo: LivenessCameraResult['photo'] & {
    readonly delete: ReturnType<typeof jest.fn<() => Promise<void>>>;
  };
} {
  return {
    photo: {
      uri,
      delete: jest.fn(async () => undefined),
    },
    livenessEvidence: {
      version: 1,
      method: 'mlkit_challenge',
      passed: true,
      challenges: ['turn_left', 'eyes_closed_hold'],
      startedAt: '2026-09-23T08:00:00.000Z',
      completedAt: '2026-09-23T08:00:05.000Z',
      engine: 'uniattend-mobile-liveness',
    },
  };
}

function createDeferred<T>(): Deferred<T> {
  let resolvePromise: ((value: T) => void) | undefined;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });

  return {
    promise,
    resolve: (value) => {
      if (!resolvePromise) {
        throw new Error('Deferred Promise is not ready to resolve');
      }

      resolvePromise(value);
    },
  };
}

function createService(result: FaceVerificationResult) {
  const verifyFace = jest.fn<FaceVerificationService['verifyFace']>();
  verifyFace.mockResolvedValue(result);

  return {
    service: { verifyFace },
    verifyFace,
  };
}

function createScreenProps(faceVerificationService: FaceVerificationService) {
  return {
    faceVerificationService,
    livenessMode: 'off' as const,
    onBack: jest.fn(),
    onFaceVerified: jest.fn(),
    sessionId: 'attendance-session-active',
  };
}

type RenderedScreen = Awaited<ReturnType<typeof render>>;

async function openCamera(screen: RenderedScreen) {
  await fireEvent.press(
    screen.getByRole('button', { name: 'Begin face verification' }),
  );
  await screen.findByText('Capture & Verify');
}

async function captureAndVerify(screen: RenderedScreen) {
  await openCamera(screen);
  await fireEvent.press(
    screen.getByRole('button', { name: 'Begin face verification' }),
  );
}

describe('FaceVerificationScreen', () => {
  beforeEach(() => {
    mockLivenessOnSuccess = undefined;
    mockLivenessSessionStarts = 0;
    mockLocalLivenessOutcome = 'Liveness running';
    mockPermissionState = { granted: true };
    mockRequestCameraPermission.mockReset();
    mockRequestCameraPermission.mockResolvedValue({ granted: true });
    mockTakePictureAsync.mockReset();
    mockTakePictureAsync.mockResolvedValue({
      uri: 'file:///face-capture.jpg',
    });
  });

  test('uses local liveness when livenessMode is omitted', async () => {
    const { service, verifyFace } = createService({ status: 'success' });
    const { livenessMode: _livenessMode, ...existingProps } =
      createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen {...existingProps} />,
    );

    expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();
    expect(screen.queryByLabelText('Face camera placeholder')).toBeNull();
    expect(mockLivenessSessionStarts).toBe(1);
    expect(verifyFace).not.toHaveBeenCalled();
  });

  test('uses local liveness when livenessMode is required', async () => {
    const { service } = createService({ status: 'success' });
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps(service)}
        livenessMode="required"
      />,
    );

    expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();
    expect(screen.queryByLabelText('Face camera placeholder')).toBeNull();
  });

  test('submits one successful liveness result with its exact photo and evidence', async () => {
    const deferred = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => deferred.promise,
    );
    const result = createSuccessfulLivenessResult();
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps({ verifyFace })}
        livenessMode="required"
      />,
    );

    await act(async () => {
      mockLivenessOnSuccess?.(result);
    });

    expect(screen.queryByLabelText('Local liveness camera')).toBeNull();
    expect(screen.getByText('Verifying your face...')).toBeTruthy();
    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(verifyFace).toHaveBeenCalledWith({
      sessionId: 'attendance-session-active',
      capture: { uri: result.photo.uri },
      livenessEvidence: result.livenessEvidence,
    });
    expect(verifyFace.mock.calls[0][0].livenessEvidence)
      .toBe(result.livenessEvidence);
    expect(verifyFace.mock.calls[0][0].livenessEvidence?.challenges).toEqual([
      'turn_left',
      'eyes_closed_hold',
    ]);

    await act(async () => {
      mockLivenessOnSuccess?.(result);
    });
    expect(verifyFace).toHaveBeenCalledTimes(1);

    await act(async () => {
      deferred.resolve({ status: 'success' });
      await deferred.promise;
    });

    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(result.photo.delete).toHaveBeenCalledTimes(1);
  });

  test('completes the required flow through MockFaceVerificationService', async () => {
    const service = new MockFaceVerificationService({
      result: { status: 'success' },
    });
    const verifyFace = jest.spyOn(service, 'verifyFace');
    const props = createScreenProps(service);
    const result = createSuccessfulLivenessResult(
      'file:///mock-service-final-photo.jpg',
    );
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        livenessMode="required"
      />,
    );

    const successCallback = mockLivenessOnSuccess;
    await act(async () => {
      successCallback?.(result);
      successCallback?.(result);
    });

    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(verifyFace).toHaveBeenCalledWith({
      sessionId: 'attendance-session-active',
      capture: { uri: result.photo.uri },
      livenessEvidence: result.livenessEvidence,
    });
    expect(props.onFaceVerified).not.toHaveBeenCalled();

    const continueButton = screen.getByRole('button', {
      name: 'Continue to attendance progress',
    });
    await fireEvent.press(continueButton);
    await fireEvent.press(continueButton);

    expect(props.onFaceVerified).toHaveBeenCalledTimes(1);
    expect(props.onFaceVerified).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test('preserves the verified flow and continues only after the user confirms', async () => {
    const { service } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const result = createSuccessfulLivenessResult();
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        livenessMode="required"
      />,
    );

    await act(async () => {
      mockLivenessOnSuccess?.(result);
    });

    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();

    await fireEvent.press(
      screen.getByRole('button', { name: 'Continue to attendance progress' }),
    );
    expect(props.onFaceVerified).toHaveBeenCalledTimes(1);
    expect(props.onFaceVerified).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test.each([
    {
      result: { status: 'face_not_detected', canRetry: true } as const,
      title: 'Face not detected',
    },
    {
      result: { status: 'multiple_faces', canRetry: true } as const,
      title: 'Multiple faces detected',
    },
    {
      result: { status: 'verification_failure', canRetry: true } as const,
      title: 'Face verification failed',
    },
  ])(
    'keeps $result.status distinct and retries it through fresh liveness',
    async ({ result, title }) => {
      const { service, verifyFace } = createService(result);
      const props = createScreenProps(service);
      const livenessResult = createSuccessfulLivenessResult();
      const screen = await render(
        <FaceVerificationScreen
          {...props}
          livenessMode="required"
        />,
      );

      await act(async () => {
        mockLivenessOnSuccess?.(livenessResult);
      });

      expect(await screen.findByText(title)).toBeTruthy();
      expect(props.onFaceVerified).not.toHaveBeenCalled();
      expect(verifyFace).toHaveBeenCalledTimes(1);

      await fireEvent.press(
        screen.getByRole('button', { name: 'Retry face verification' }),
      );

      expect(mockLivenessSessionStarts).toBe(2);
      expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();
      expect(verifyFace).toHaveBeenCalledTimes(1);
    },
  );

  test('preserves a terminal biometric result after required liveness', async () => {
    const { service } = createService({
      status: 'verification_failure',
      canRetry: false,
    });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        livenessMode="required"
      />,
    );

    await act(async () => {
      mockLivenessOnSuccess?.(createSuccessfulLivenessResult());
    });

    expect(await screen.findByText('Face verification failed')).toBeTruthy();
    expect(
      screen.getByText(
        'No face verification attempts remain for this session.',
      ),
    ).toBeTruthy();
    expect(
      screen.queryByRole('button', { name: 'Retry face verification' }),
    ).toBeNull();
    expect(
      screen.getByRole('button', { name: 'Return to attendance session' }),
    ).toBeTruthy();
  });

  test.each([
    'Challenge failed',
    'Challenge timed out',
    'Session timed out',
    'No face detected locally',
    'Multiple faces detected locally',
    'Face too small locally',
    'Camera capture failed locally',
    'ML Kit processing failed locally',
    'Liveness cancelled locally',
  ])('does not submit after local outcome: %s', async (outcome) => {
    mockLocalLivenessOutcome = outcome;
    const { service, verifyFace } = createService({ status: 'success' });
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps(service)}
        livenessMode="required"
      />,
    );

    expect(screen.getByText(outcome)).toBeTruthy();
    expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();
    expect(verifyFace).not.toHaveBeenCalled();
  });

  test('does not submit a completed result delivered after cancellation or unmount', async () => {
    const { service, verifyFace } = createService({ status: 'success' });
    const staleResult = createSuccessfulLivenessResult(
      'file:///stale-liveness-photo.jpg',
    );
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps(service)}
        livenessMode="required"
      />,
    );
    const staleSuccessCallback = mockLivenessOnSuccess;

    await screen.unmount();
    await act(async () => {
      staleSuccessCallback?.(staleResult);
    });

    expect(verifyFace).not.toHaveBeenCalled();
    expect(staleResult.photo.delete).toHaveBeenCalledTimes(1);
  });

  test('invalidates a pending request and stale liveness callbacks immediately on exit', async () => {
    const pendingResult = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => pendingResult.promise,
    );
    const props = createScreenProps({ verifyFace });
    const activeResult = createSuccessfulLivenessResult(
      'file:///cancelled-request-photo.jpg',
    );
    const staleResult = createSuccessfulLivenessResult(
      'file:///post-cancel-stale-photo.jpg',
    );
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        livenessMode="required"
      />,
    );
    const cancelledSessionCallback = mockLivenessOnSuccess;

    await act(async () => {
      cancelledSessionCallback?.(activeResult);
    });
    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Verifying your face...')).toBeTruthy();

    await fireEvent.press(screen.getByRole('button', { name: 'Go back' }));
    await waitFor(() => {
      expect(activeResult.photo.delete).toHaveBeenCalledTimes(1);
    });
    expect(props.onBack).toHaveBeenCalledTimes(1);

    await act(async () => {
      cancelledSessionCallback?.(staleResult);
    });
    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(staleResult.photo.delete).toHaveBeenCalledTimes(1);

    await act(async () => {
      pendingResult.resolve({ status: 'success' });
      await pendingResult.promise;
    });

    expect(screen.queryByText('Face verified')).toBeNull();
    expect(props.onFaceVerified).not.toHaveBeenCalled();
  });

  test('does not submit a stale replacement result while an action is active', async () => {
    const deferred = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => deferred.promise,
    );
    const acceptedResult = createSuccessfulLivenessResult();
    const staleResult = createSuccessfulLivenessResult(
      'file:///stale-liveness-photo.jpg',
    );
    await render(
      <FaceVerificationScreen
        {...createScreenProps({ verifyFace })}
        livenessMode="required"
      />,
    );

    await act(async () => {
      mockLivenessOnSuccess?.(acceptedResult);
      mockLivenessOnSuccess?.(staleResult);
    });

    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(verifyFace.mock.calls[0][0].capture.uri)
      .toBe(acceptedResult.photo.uri);
    expect(staleResult.photo.delete).toHaveBeenCalledTimes(1);

    await act(async () => {
      deferred.resolve({ status: 'success' });
      await deferred.promise;
    });
  });

  test('discards a rejected backend liveness result and requires a fresh session', async () => {
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>();
    verifyFace
      .mockResolvedValueOnce({ status: 'liveness_failure', canRetry: true })
      .mockResolvedValueOnce({ status: 'success' });
    const rejectedResult = createSuccessfulLivenessResult(
      'file:///rejected-liveness-photo.jpg',
    );
    const freshResult = createSuccessfulLivenessResult(
      'file:///fresh-liveness-photo.jpg',
    );
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps({ verifyFace })}
        livenessMode="required"
      />,
    );
    const rejectedSessionCallback = mockLivenessOnSuccess;

    await act(async () => {
      rejectedSessionCallback?.(rejectedResult);
    });

    await waitFor(() => {
      expect(mockLivenessSessionStarts).toBe(2);
    });
    expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();
    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(rejectedResult.photo.delete).toHaveBeenCalledTimes(1);

    await act(async () => {
      rejectedSessionCallback?.(rejectedResult);
    });
    expect(verifyFace).toHaveBeenCalledTimes(1);

    const freshSessionCallback = mockLivenessOnSuccess;
    await act(async () => {
      freshSessionCallback?.(freshResult);
    });

    expect(verifyFace).toHaveBeenCalledTimes(2);
    expect(verifyFace.mock.calls[1][0]).toEqual({
      sessionId: 'attendance-session-active',
      capture: { uri: freshResult.photo.uri },
      livenessEvidence: freshResult.livenessEvidence,
    });
    expect(verifyFace.mock.calls[1][0].livenessEvidence)
      .toBe(freshResult.livenessEvidence);
    expect(verifyFace.mock.calls[1][0].livenessEvidence)
      .not.toBe(rejectedResult.livenessEvidence);
    expect(await screen.findByText('Face verified')).toBeTruthy();
  });

  test('shows a retryable 503 state and retries through fresh liveness without overlap', async () => {
    const retryResult = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>();
    verifyFace
      .mockResolvedValueOnce({ status: 'service_unavailable', canRetry: true })
      .mockImplementationOnce(() => retryResult.promise);
    const firstResult = createSuccessfulLivenessResult(
      'file:///unavailable-session-photo.jpg',
    );
    const freshResult = createSuccessfulLivenessResult(
      'file:///retry-session-photo.jpg',
    );
    const props = createScreenProps({ verifyFace });
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        livenessMode="required"
      />,
    );

    await act(async () => {
      mockLivenessOnSuccess?.(firstResult);
    });

    expect(
      await screen.findByText('Face verification is temporarily unavailable'),
    ).toBeTruthy();
    expect(
      screen.getByText('The verification service is unavailable. Please try again.'),
    ).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();
    expect(firstResult.photo.delete).toHaveBeenCalledTimes(1);

    const retryButton = screen.getByRole('button', {
      name: 'Retry face verification',
    });
    await fireEvent.press(retryButton);
    await fireEvent.press(retryButton);

    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(mockLivenessSessionStarts).toBe(2);
    expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();

    await act(async () => {
      mockLivenessOnSuccess?.(freshResult);
      mockLivenessOnSuccess?.(freshResult);
    });

    expect(verifyFace).toHaveBeenCalledTimes(2);
    expect(verifyFace.mock.calls[1][0]).toEqual({
      sessionId: 'attendance-session-active',
      capture: { uri: freshResult.photo.uri },
      livenessEvidence: freshResult.livenessEvidence,
    });
    expect(screen.getByText('Verifying your face...')).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();

    await act(async () => {
      retryResult.resolve({ status: 'success' });
      await retryResult.promise;
    });

    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(freshResult.photo.delete).toHaveBeenCalledTimes(1);
  });

  test('completes the legacy flow without starting liveness or sending evidence', async () => {
    const { service, verifyFace } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        livenessMode="off"
      />,
    );

    expect(screen.getByLabelText('Face camera placeholder')).toBeTruthy();
    expect(screen.queryByLabelText('Local liveness camera')).toBeNull();
    expect(mockLivenessSessionStarts).toBe(0);

    await captureAndVerify(screen);

    expect(verifyFace).toHaveBeenCalledTimes(1);
    expect(verifyFace).toHaveBeenCalledWith({
      sessionId: 'attendance-session-active',
      capture: { uri: 'file:///face-capture.jpg' },
    });
    expect('livenessEvidence' in verifyFace.mock.calls[0][0]).toBe(false);
    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();

    await fireEvent.press(
      screen.getByRole('button', { name: 'Continue to attendance progress' }),
    );
    expect(props.onFaceVerified).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test('keeps all existing required props compatible', async () => {
    const { service } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen
        faceVerificationService={props.faceVerificationService}
        onBack={props.onBack}
        onFaceVerified={props.onFaceVerified}
        sessionId={props.sessionId}
      />,
    );

    expect(
      screen.getByRole('header', { name: 'Face Verification' }),
    ).toBeTruthy();
    expect(screen.getByLabelText('Local liveness camera')).toBeTruthy();
  });

  test('shows a concise ready state, camera placeholder, privacy notice, and no QR action', async () => {
    const { service } = createService({ status: 'success' });
    const {
      getByLabelText,
      getByRole,
      getByText,
      queryByText,
    } = await render(
      <FaceVerificationScreen {...createScreenProps(service)} />,
    );

    expect(
      getByRole('header', { name: 'Face Verification' }),
    ).toBeTruthy();
    expect(getByText('Ready for face verification')).toBeTruthy();
    expect(
      getByText('Position your face inside the frame and begin verification.'),
    ).toBeTruthy();
    expect(getByLabelText('Face camera placeholder')).toBeTruthy();
    expect(
      getByText(
        'Your face is used only for attendance verification and should not be stored unnecessarily.',
      ),
    ).toBeTruthy();
    expect(
      getByRole('button', { name: 'Begin face verification' }),
    ).toBeTruthy();
    expect(
      queryByText(/Scan QR|Waiting for QR|Mandatory QR verification|QR scanner/i),
    ).toBeNull();
    expect(
      queryByText('Remove sunglasses or anything covering your face.'),
    ).toBeNull();
  });

  test('reuses the camera flow for readiness without attendance progress', async () => {
    const { service } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen
        {...props}
        mode="readiness"
      />,
    );

    expect(screen.queryByText('Location')).toBeNull();
    expect(
      screen.getByRole('header', { name: 'Face Readiness Check' }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        'Your face is used only for readiness verification and should not be stored unnecessarily.',
      ),
    ).toBeTruthy();

    await captureAndVerify(screen);
    expect(await screen.findByText('Readiness check passed')).toBeTruthy();
    expect(
      screen.getByText('Face verification is ready to use for attendance.'),
    ).toBeTruthy();
    expect(screen.queryByText('Native front camera')).toBeNull();
    await fireEvent.press(
      await screen.findByRole('button', { name: 'Return to dashboard' }),
    );

    expect(props.onFaceVerified).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test('requests camera permission from Begin Verification before showing the front camera', async () => {
    mockPermissionState = { granted: false };
    const { service, verifyFace } = createService({ status: 'success' });
    const screen = await render(
      <FaceVerificationScreen {...createScreenProps(service)} />,
    );

    await fireEvent.press(
      screen.getByRole('button', { name: 'Begin face verification' }),
    );

    expect(mockRequestCameraPermission).toHaveBeenCalledTimes(1);
    expect(await screen.findByLabelText('Front camera preview')).toBeTruthy();
    expect(await screen.findByText('Camera ready')).toBeTruthy();
    expect(verifyFace).not.toHaveBeenCalled();
  });

  test('shows a safe message when camera permission is denied', async () => {
    mockPermissionState = { granted: false };
    mockRequestCameraPermission.mockResolvedValueOnce({ granted: false });
    const { service, verifyFace } = createService({ status: 'success' });
    const screen = await render(
      <FaceVerificationScreen {...createScreenProps(service)} />,
    );

    await fireEvent.press(
      screen.getByRole('button', { name: 'Begin face verification' }),
    );

    expect(
      await screen.findByText('Camera permission required'),
    ).toBeTruthy();
    expect(screen.queryByLabelText('Front camera preview')).toBeNull();
    expect(verifyFace).not.toHaveBeenCalled();
  });

  test('begins verification with the correct request and exposes the processing state', async () => {
    const deferred = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => deferred.promise,
    );
    const props = createScreenProps({ verifyFace });
    const screen = await render(
      <FaceVerificationScreen {...props} />,
    );

    await captureAndVerify(screen);

    expect(verifyFace).toHaveBeenCalledWith({
      sessionId: 'attendance-session-active',
      capture: { uri: 'file:///face-capture.jpg' },
    });
    expect(screen.getByText('Verifying your face...')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: 'Begin face verification' }).props
        .accessibilityState,
    ).toEqual({ busy: true, disabled: true });

    await act(async () => {
      deferred.resolve({ status: 'verification_failure' });
      await deferred.promise;
    });
  });

  test('replaces the readiness camera with verifying and result screens after capture', async () => {
    const deferred = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => deferred.promise,
    );
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps({ verifyFace })}
        mode="readiness"
      />,
    );

    await captureAndVerify(screen);

    expect(screen.queryByText('Native front camera')).toBeNull();
    expect(
      screen.getByLabelText('Readiness verification in progress'),
    ).toBeTruthy();
    expect(screen.getByText('Verifying readiness...')).toBeTruthy();
    expect(
      screen.queryByText(
        'Photo captured. You can relax while we check your face.',
      ),
    ).toBeNull();

    await act(async () => {
      deferred.resolve({ status: 'success' });
      await deferred.promise;
    });

    expect(screen.getByLabelText('Readiness check passed')).toBeTruthy();
    expect(screen.getByText('Readiness check passed')).toBeTruthy();
    expect(
      screen.getByText('Face verification is ready to use for attendance.'),
    ).toBeTruthy();
  });

  test('returns to the camera before retrying a failed readiness check', async () => {
    const { service, verifyFace } = createService({
      status: 'verification_failure',
    });
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps(service)}
        mode="readiness"
      />,
    );

    await captureAndVerify(screen);

    expect(await screen.findByText('Readiness check failed')).toBeTruthy();
    expect(screen.queryByText('Native front camera')).toBeNull();

    await fireEvent.press(
      screen.getByRole('button', { name: 'Retry face verification' }),
    );

    expect(await screen.findByText('Native front camera')).toBeTruthy();
    expect(await screen.findByText('Capture & Verify')).toBeTruthy();
    expect(verifyFace).toHaveBeenCalledTimes(1);
  });

  test('prevents duplicate verification requests while processing', async () => {
    const deferred = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => deferred.promise,
    );
    const screen = await render(
      <FaceVerificationScreen
        {...createScreenProps({ verifyFace })}
      />,
    );

    await openCamera(screen);
    const beginButton = screen.getByRole('button', {
      name: 'Begin face verification',
    });

    await fireEvent.press(beginButton);
    await fireEvent.press(beginButton);
    await fireEvent.press(beginButton);

    expect(verifyFace).toHaveBeenCalledTimes(1);

    await act(async () => {
      deferred.resolve({ status: 'face_not_detected' });
      await deferred.promise;
    });
  });

  test('shows success without invoking the callback until Continue is pressed', async () => {
    const { service } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen {...props} />,
    );

    await captureAndVerify(screen);

    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(
      await screen.findByText(
        'Your identity has been successfully verified.',
      ),
    ).toBeTruthy();
    expect(
      await screen.findByRole('button', {
        name: 'Continue to attendance progress',
      }),
    ).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();
  });

  test('continues exactly once with the current session after success', async () => {
    const { service } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen {...props} />,
    );

    await captureAndVerify(screen);
    const continueButton = await screen.findByRole('button', {
      name: 'Continue to attendance progress',
    });

    await fireEvent.press(continueButton);
    await fireEvent.press(continueButton);

    expect(props.onFaceVerified).toHaveBeenCalledTimes(1);
    expect(props.onFaceVerified).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test.each(failureOutcomes)(
    'shows the $result.status result and allows another attempt',
    async ({ result, title, message }) => {
      const { service } = createService(result);
      const props = createScreenProps(service);
      const screen = await render(
        <FaceVerificationScreen {...props} />,
      );

      await captureAndVerify(screen);

      expect(await screen.findByText(title)).toBeTruthy();
      expect(await screen.findByText(message)).toBeTruthy();
      expect(
        await screen.findByRole('button', {
          name: 'Retry face verification',
        }),
      ).toBeTruthy();
      expect(props.onFaceVerified).not.toHaveBeenCalled();
    },
  );

  test('maps an unexpected rejection to a safe retryable error', async () => {
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>();
    verifyFace.mockRejectedValue(new Error('internal error'));
    const props = createScreenProps({ verifyFace });
    const screen = await render(
      <FaceVerificationScreen {...props} />,
    );

    await captureAndVerify(screen);

    expect(
      await screen.findByText("We couldn't complete face verification"),
    ).toBeTruthy();
    expect(
      await screen.findByText('Something went wrong. Please try again.'),
    ).toBeTruthy();
    expect(screen.queryByText('internal error')).toBeNull();
    expect(
      await screen.findByRole('button', {
        name: 'Retry face verification',
      }),
    ).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();
  });

  test('does not offer another capture after the final attendance face attempt', async () => {
    const { service } = createService({
      status: 'verification_failure',
      canRetry: false,
    });
    const props = createScreenProps(service);
    const screen = await render(
      <FaceVerificationScreen {...props} />,
    );

    await captureAndVerify(screen);

    expect(await screen.findByText('Face verification failed')).toBeTruthy();
    expect(
      await screen.findByText(
        'No face verification attempts remain for this session.',
      ),
    ).toBeTruthy();
    expect(
      screen.queryByRole('button', { name: 'Retry face verification' }),
    ).toBeNull();
    expect(
      screen.getByRole('button', { name: 'Return to attendance session' }),
    ).toBeTruthy();
  });

  test('retry starts a new request, shows processing, and then shows success', async () => {
    const retryResult = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>();
    verifyFace
      .mockResolvedValueOnce({ status: 'face_not_detected' })
      .mockImplementationOnce(() => retryResult.promise);
    const props = createScreenProps({ verifyFace });
    const screen = await render(<FaceVerificationScreen {...props} />);

    await captureAndVerify(screen);
    expect(await screen.findByText('Face not detected')).toBeTruthy();

    await fireEvent.press(
      await screen.findByRole('button', {
        name: 'Retry face verification',
      }),
    );

    expect(verifyFace).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Verifying your face...')).toBeTruthy();
    expect(screen.queryByText('Face not detected')).toBeNull();

    await act(async () => {
      retryResult.resolve({ status: 'success' });
      await retryResult.promise;
    });

    expect(await screen.findByText('Face verified')).toBeTruthy();
    expect(props.onFaceVerified).not.toHaveBeenCalled();
  });

  test('does not update or navigate when a pending request resolves after unmount', async () => {
    const pendingResult = createDeferred<FaceVerificationResult>();
    const verifyFace = jest.fn<FaceVerificationService['verifyFace']>(
      () => pendingResult.promise,
    );
    const props = createScreenProps({ verifyFace });
    const screen = await render(
      <FaceVerificationScreen {...props} />,
    );

    await captureAndVerify(screen);
    await screen.unmount();

    await act(async () => {
      pendingResult.resolve({ status: 'success' });
      await pendingResult.promise;
    });

    expect(props.onFaceVerified).not.toHaveBeenCalled();
  });

  test('uses the accessible back action without starting verification', async () => {
    const { service, verifyFace } = createService({ status: 'success' });
    const props = createScreenProps(service);
    const { getByRole } = await render(
      <FaceVerificationScreen {...props} />,
    );

    await fireEvent.press(getByRole('button', { name: 'Go back' }));

    expect(props.onBack).toHaveBeenCalledTimes(1);
    expect(verifyFace).not.toHaveBeenCalled();
    expect(props.onFaceVerified).not.toHaveBeenCalled();
  });
});
