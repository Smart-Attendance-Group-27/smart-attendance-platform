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
} from '@testing-library/react-native';

import { FaceVerificationScreen } from '../screens/FaceVerificationScreen';
import type { FaceVerificationService } from '../services/faceVerificationService';
import type { FaceVerificationResult } from '../types/faceVerification';

const mockRequestCameraPermission = jest.fn<
  () => Promise<{ granted: boolean }>
>();
const mockTakePictureAsync = jest.fn<
  () => Promise<{ uri: string }>
>();
let mockPermissionState: { granted: boolean } | null = { granted: true };

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
    mockPermissionState = { granted: true };
    mockRequestCameraPermission.mockReset();
    mockRequestCameraPermission.mockResolvedValue({ granted: true });
    mockTakePictureAsync.mockReset();
    mockTakePictureAsync.mockResolvedValue({
      uri: 'file:///face-capture.jpg',
    });
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
      screen.getByText(
        'Your face is used only for readiness verification and should not be stored unnecessarily.',
      ),
    ).toBeTruthy();

    await captureAndVerify(screen);
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
    expect(screen.getByText('Please keep your face steady.')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: 'Begin face verification' }).props
        .accessibilityState,
    ).toEqual({ busy: true, disabled: true });

    await act(async () => {
      deferred.resolve({ status: 'verification_failure' });
      await deferred.promise;
    });
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
        name: 'Continue to QR scanner',
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
      name: 'Continue to QR scanner',
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
