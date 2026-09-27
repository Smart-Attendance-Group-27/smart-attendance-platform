import { CameraView, useCameraPermissions } from 'expo-camera';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import {
  useEffect,
  useRef,
  useState,
  type RefObject,
} from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';
import { AttendanceProgressSteps } from '../../attendance/components/AttendanceProgressSteps';
import {
  LivenessCamera,
  type LivenessCameraResult,
} from '../components/LivenessCamera';
import type { FaceVerificationService } from '../services/faceVerificationService';
import type { FaceVerificationResult } from '../types/faceVerification';

type FaceVerificationScreenProps = {
  sessionId: string;
  faceVerificationService: FaceVerificationService;
  /**
   * Controls only the mobile-side liveness flow. `off` is for compatibility
   * with environments where server enforcement is disabled; it never bypasses
   * face-service liveness enforcement.
   */
  livenessMode?: 'required' | 'off';
  mode?: 'attendance' | 'readiness';
  onBack: () => void;
  onFaceVerified: (sessionId: string) => void;
};

type FaceVerificationUiState =
  | { status: 'ready' }
  | { status: 'requesting_camera_permission' }
  | { status: 'camera_ready' }
  | { status: 'camera_permission_denied' }
  | { status: 'camera_error' }
  | { status: 'capturing' }
  | { status: 'processing' }
  | Exclude<FaceVerificationResult, { status: 'success' }>
  | { status: 'unexpected_error' }
  | { status: 'success' };

type StatusTone = 'info' | 'success' | 'error';

type StatusContent = {
  icon: SymbolViewProps['name'];
  title: string;
  message?: string;
  tone: StatusTone;
};

const statusContent: Record<
  FaceVerificationUiState['status'],
  StatusContent
> = {
  ready: {
    icon: {
      ios: 'viewfinder',
      android: 'center_focus_strong',
      web: 'center_focus_strong',
    },
    title: 'Ready for face verification',
    message: 'Position your face inside the frame and begin verification.',
    tone: 'info',
  },
  requesting_camera_permission: {
    icon: {
      ios: 'camera.fill',
      android: 'photo_camera',
      web: 'photo_camera',
    },
    title: 'Requesting camera access...',
    message: 'Allow camera access to continue with face verification.',
    tone: 'info',
  },
  camera_ready: {
    icon: {
      ios: 'camera.fill',
      android: 'photo_camera',
      web: 'photo_camera',
    },
    title: 'Camera ready',
    message: 'Position your face inside the guide, then capture and verify.',
    tone: 'info',
  },
  camera_permission_denied: {
    icon: {
      ios: 'camera.fill',
      android: 'no_photography',
      web: 'no_photography',
    },
    title: 'Camera permission required',
    message: 'Allow camera access to verify your face for attendance.',
    tone: 'error',
  },
  camera_error: {
    icon: {
      ios: 'exclamationmark.triangle.fill',
      android: 'camera_alt',
      web: 'camera_alt',
    },
    title: "We couldn't start the camera",
    message: 'Check that the camera is available, then try again.',
    tone: 'error',
  },
  capturing: {
    icon: {
      ios: 'camera.fill',
      android: 'photo_camera',
      web: 'photo_camera',
    },
    title: 'Capturing photo...',
    message: 'Hold still for just a moment.',
    tone: 'info',
  },
  processing: {
    icon: {
      ios: 'face.smiling',
      android: 'face',
      web: 'face',
    },
    title: 'Verifying your face...',
    message: 'Your photo was captured. You can relax while we verify it.',
    tone: 'info',
  },
  success: {
    icon: {
      ios: 'checkmark.circle.fill',
      android: 'check_circle',
      web: 'check_circle',
    },
    title: 'Face verified',
    message: 'Your identity has been successfully verified.',
    tone: 'success',
  },
  face_not_detected: {
    icon: {
      ios: 'person.crop.circle.badge.questionmark',
      android: 'person_search',
      web: 'person_search',
    },
    title: 'Face not detected',
    message:
      'Make sure your face is clearly visible inside the frame and try again.',
    tone: 'error',
  },
  multiple_faces: {
    icon: {
      ios: 'person.2.fill',
      android: 'group',
      web: 'group',
    },
    title: 'Multiple faces detected',
    message: 'Make sure only your face is visible in the camera frame.',
    tone: 'error',
  },
  liveness_failure: {
    icon: {
      ios: 'exclamationmark.triangle.fill',
      android: 'warning',
      web: 'warning',
    },
    title: 'Verification could not confirm liveness',
    message: 'Keep your face visible and steady, then try again.',
    tone: 'error',
  },
  service_unavailable: {
    icon: {
      ios: 'exclamationmark.circle.fill',
      android: 'error',
      web: 'error',
    },
    title: 'Face verification is temporarily unavailable',
    message: 'The verification service is unavailable. Please try again.',
    tone: 'error',
  },
  verification_failure: {
    icon: {
      ios: 'xmark.circle.fill',
      android: 'cancel',
      web: 'cancel',
    },
    title: 'Face verification failed',
    message: "We couldn't verify your face. Please try again.",
    tone: 'error',
  },
  unexpected_error: {
    icon: {
      ios: 'exclamationmark.circle.fill',
      android: 'error',
      web: 'error',
    },
    title: "We couldn't complete face verification",
    message: 'Something went wrong. Please try again.',
    tone: 'error',
  },
};

const readinessStatusContent: Partial<
  Record<FaceVerificationUiState['status'], StatusContent>
> = {
  processing: {
    icon: {
      ios: 'face.smiling',
      android: 'face',
      web: 'face',
    },
    title: 'Verifying readiness...',
    tone: 'info',
  },
  success: {
    icon: {
      ios: 'checkmark.circle.fill',
      android: 'check_circle',
      web: 'check_circle',
    },
    title: 'Readiness check passed',
    message: 'Face verification is ready to use for attendance.',
    tone: 'success',
  },
  verification_failure: {
    icon: {
      ios: 'xmark.circle.fill',
      android: 'cancel',
      web: 'cancel',
    },
    title: 'Readiness check failed',
    message: "We couldn't verify your face. Please try again.",
    tone: 'error',
  },
};

function ScreenHeader({
  onBack,
  title,
}: {
  onBack: () => void;
  title: string;
}) {
  return (
    <View style={styles.header}>
      <Pressable
        accessibilityLabel="Go back"
        accessibilityRole="button"
        hitSlop={spacing.xs}
        onPress={onBack}
        style={({ pressed }) => [
          styles.backButton,
          pressed && styles.pressed,
        ]}
      >
        <SymbolView
          name={{
            ios: 'chevron.left',
            android: 'arrow_back',
            web: 'arrow_back',
          }}
          size={22}
          tintColor={lightColors.textPrimary}
        />
      </Pressable>
      <Text accessibilityRole="header" style={styles.screenTitle}>
        {title}
      </Text>
    </View>
  );
}

function VerificationStage({
  content,
  processing,
}: {
  content: StatusContent;
  processing: boolean;
}) {
  return (
    <View
      accessible
      accessibilityLabel={
        processing ? 'Readiness verification in progress' : content.title
      }
      accessibilityLiveRegion="polite"
      accessibilityRole={content.tone === 'error' ? 'alert' : undefined}
      accessibilityState={{ busy: processing }}
      style={[
        styles.cameraContainer,
        styles.verificationStage,
        statusContainerStyles[content.tone],
      ]}
    >
      {processing ? (
        <ActivityIndicator
          accessibilityLabel="Readiness verification processing"
          color={lightColors.primaryInteraction}
          size="large"
        />
      ) : (
        <SymbolView
          name={content.icon}
          size={64}
          tintColor={statusIconColors[content.tone]}
        />
      )}
      <Text
        style={[
          styles.verificationStageTitle,
          statusTitleStyles[content.tone],
        ]}
      >
        {content.title}
      </Text>
      {content.message ? (
        <Text style={styles.verificationStageMessage}>{content.message}</Text>
      ) : null}
    </View>
  );
}

function FaceCameraPreview({
  cameraActive,
  cameraRef,
  onCameraError,
  onCameraReady,
  processing,
}: {
  cameraActive: boolean;
  cameraRef: RefObject<CameraView | null>;
  onCameraError: () => void;
  onCameraReady: () => void;
  processing: boolean;
}) {
  return (
    <View
      accessible
      accessibilityLabel={
        cameraActive ? 'Front camera preview' : 'Face camera placeholder'
      }
      accessibilityState={{ busy: processing }}
      style={styles.cameraContainer}
    >
      {cameraActive ? (
        <CameraView
          facing="front"
          mirror
          mode="picture"
          onCameraReady={onCameraReady}
          onMountError={onCameraError}
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
        />
      ) : (
        <View style={styles.cameraPlaceholder}>
          <SymbolView
            name={{
              ios: 'camera.fill',
              android: 'photo_camera',
              web: 'photo_camera',
            }}
            size={48}
            tintColor={lightColors.primaryInteraction}
          />
          <Text style={styles.cameraPlaceholderTitle}>Camera preview</Text>
          <Text style={styles.cameraPlaceholderText}>
            Camera access starts only when you begin verification.
          </Text>
        </View>
      )}

      {cameraActive ? (
        <View pointerEvents="none" style={styles.faceGuide}>
          <View style={styles.faceFrame} />
          <Text style={styles.cameraGuidance}>
            Keep your face inside the guide
          </Text>
        </View>
      ) : null}

      {processing ? (
        <View pointerEvents="none" style={styles.processingOverlay}>
          <ActivityIndicator
            accessibilityLabel="Face verification processing"
            color={lightColors.surface}
            size="large"
          />
        </View>
      ) : null}
    </View>
  );
}

function StatusCard({
  content,
  processing,
}: {
  content: StatusContent;
  processing: boolean;
}) {
  return (
    <View
      accessible
      accessibilityLiveRegion="polite"
      accessibilityRole={content.tone === 'error' ? 'alert' : undefined}
      accessibilityState={{ busy: processing }}
      style={[
        styles.statusCard,
        statusContainerStyles[content.tone],
      ]}
    >
      <SymbolView
        name={content.icon}
        size={26}
        tintColor={statusIconColors[content.tone]}
      />
      <View style={styles.statusCopy}>
        <Text
          style={[
            styles.statusTitle,
            statusTitleStyles[content.tone],
          ]}
        >
          {content.title}
        </Text>
        {content.message ? (
          <Text style={styles.statusMessage}>{content.message}</Text>
        ) : null}
      </View>
    </View>
  );
}

function VerificationAction({
  cameraReady,
  continueAccessibilityLabel,
  continueTitle,
  state,
  onContinue,
  onExit,
  onOpenCamera,
  onVerify,
}: {
  cameraReady: boolean;
  continueAccessibilityLabel: string;
  continueTitle: string;
  state: FaceVerificationUiState;
  onContinue: () => void;
  onExit: () => void;
  onOpenCamera: () => void;
  onVerify: () => void;
}) {
  if (state.status === 'success') {
    return (
      <AppButton
        accessibilityLabel={continueAccessibilityLabel}
        onPress={onContinue}
        title={continueTitle}
      />
    );
  }

  if ('canRetry' in state && state.canRetry === false) {
    return (
      <AppButton
        accessibilityLabel="Return to attendance session"
        onPress={onExit}
        title="Return to Session"
      />
    );
  }

  if (
    state.status === 'requesting_camera_permission' ||
    state.status === 'capturing' ||
    state.status === 'processing'
  ) {
    const requestingPermission =
      state.status === 'requesting_camera_permission';
    const capturing = state.status === 'capturing';

    return (
      <AppButton
        accessibilityLabel="Begin face verification"
        loading
        loadingTitle={
          requestingPermission
            ? 'Requesting Camera...'
            : capturing
              ? 'Capturing Photo...'
            : 'Verifying Face...'
        }
        onPress={() => undefined}
        title="Begin Verification"
      />
    );
  }

  if (state.status === 'camera_ready') {
    return (
      <AppButton
        accessibilityLabel="Begin face verification"
        disabled={!cameraReady}
        onPress={onVerify}
        title={cameraReady ? 'Capture & Verify' : 'Starting Camera...'}
      />
    );
  }

  if (
    state.status === 'ready' ||
    state.status === 'camera_permission_denied' ||
    state.status === 'camera_error'
  ) {
    return (
      <AppButton
        accessibilityLabel="Begin face verification"
        onPress={onOpenCamera}
        title={
          state.status === 'ready'
            ? 'Begin Verification'
            : state.status === 'camera_permission_denied'
              ? 'Allow Camera Access'
              : 'Try Camera Again'
        }
      />
    );
  }

  return (
    <AppButton
      accessibilityLabel="Retry face verification"
      onPress={onVerify}
      title="Try Again"
    />
  );
}

export function FaceVerificationScreen({
  sessionId,
  faceVerificationService,
  livenessMode = 'required',
  mode = 'attendance',
  onBack,
  onFaceVerified,
}: FaceVerificationScreenProps) {
  const [permission, requestCameraPermission] = useCameraPermissions();
  const [state, setState] = useState<FaceVerificationUiState>({
    status: 'ready',
  });
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [livenessSessionKey, setLivenessSessionKey] = useState(0);
  const cameraRef = useRef<CameraView>(null);
  const activeRequest = useRef(0);
  const isMounted = useRef(true);
  const isOpeningCamera = useRef(false);
  const isProcessing = useRef(false);
  const isRestartingLiveness = useRef(false);
  const hasExited = useRef(false);
  const hasContinued = useRef(false);
  const pendingLivenessResult = useRef<LivenessCameraResult | null>(null);
  const acceptedLivenessResult = useRef<LivenessCameraResult | null>(null);
  const livenessSessionKeyRef = useRef(0);
  const discardedLivenessResults = useRef(
    new WeakSet<LivenessCameraResult>(),
  );
  const isReadinessCheck = mode === 'readiness';

  const discardLivenessResult = async (result: LivenessCameraResult) => {
    if (discardedLivenessResults.current.has(result)) {
      return;
    }

    discardedLivenessResults.current.add(result);
    await result.photo.delete().catch(() => undefined);
  };

  useEffect(() => {
    isMounted.current = true;
    const discardedResults = discardedLivenessResults.current;

    return () => {
      isMounted.current = false;
      hasExited.current = true;
      isOpeningCamera.current = false;
      isProcessing.current = false;
      activeRequest.current += 1;
      const livenessResult = pendingLivenessResult.current;
      pendingLivenessResult.current = null;
      if (
        livenessResult &&
        !discardedResults.has(livenessResult)
      ) {
        discardedResults.add(livenessResult);
        void livenessResult.photo.delete().catch(() => undefined);
      }
    };
  }, []);

  const acceptLivenessResult = (
    result: LivenessCameraResult,
    sessionKey: number,
  ) => {
    if (
      !isMounted.current ||
      hasExited.current ||
      sessionKey !== livenessSessionKeyRef.current ||
      isProcessing.current ||
      acceptedLivenessResult.current
    ) {
      if (acceptedLivenessResult.current !== result) {
        void discardLivenessResult(result);
      }
      return;
    }

    acceptedLivenessResult.current = result;
    isRestartingLiveness.current = false;
    pendingLivenessResult.current = result;
    isProcessing.current = true;
    const requestId = activeRequest.current + 1;
    activeRequest.current = requestId;
    setState({ status: 'processing' });

    void (async () => {
      let restartLiveness = false;

      try {
        const verificationResult = await faceVerificationService.verifyFace({
          sessionId,
          capture: { uri: result.photo.uri },
          livenessEvidence: result.livenessEvidence,
        });

        if (!isMounted.current || activeRequest.current !== requestId) {
          return;
        }

        if (verificationResult.status === 'liveness_failure') {
          restartLiveness = true;
        } else {
          setState(verificationResult);
        }
      } catch {
        if (isMounted.current && activeRequest.current === requestId) {
          setState({ status: 'unexpected_error' });
        }
      } finally {
        if (pendingLivenessResult.current === result) {
          pendingLivenessResult.current = null;
          await discardLivenessResult(result);
        }

        if (activeRequest.current === requestId) {
          isProcessing.current = false;

          if (restartLiveness && isMounted.current) {
            acceptedLivenessResult.current = null;
            const nextSessionKey = livenessSessionKeyRef.current + 1;
            livenessSessionKeyRef.current = nextSessionKey;
            setLivenessSessionKey(nextSessionKey);
            setState({ status: 'ready' });
          }
        }
      }
    })();
  };

  const cancelAndExit = () => {
    if (hasExited.current) {
      return;
    }

    hasExited.current = true;
    isOpeningCamera.current = false;
    isProcessing.current = false;
    isRestartingLiveness.current = false;
    activeRequest.current += 1;
    livenessSessionKeyRef.current += 1;
    acceptedLivenessResult.current = null;

    const livenessResult = pendingLivenessResult.current;
    pendingLivenessResult.current = null;
    if (livenessResult) {
      void discardLivenessResult(livenessResult);
    }

    onBack();
  };

  const retryRequiredLiveness = () => {
    if (
      hasExited.current ||
      !canRetryWithFreshLiveness(state) ||
      isProcessing.current ||
      isRestartingLiveness.current
    ) {
      return;
    }

    isRestartingLiveness.current = true;
    acceptedLivenessResult.current = null;
    const nextSessionKey = livenessSessionKeyRef.current + 1;
    livenessSessionKeyRef.current = nextSessionKey;
    setLivenessSessionKey(nextSessionKey);
    setState({ status: 'ready' });
  };

  const openCamera = async () => {
    if (
      hasExited.current ||
      isOpeningCamera.current ||
      isProcessing.current ||
      hasContinued.current
    ) {
      return;
    }

    isOpeningCamera.current = true;

    try {
      if (!permission?.granted) {
        setState({ status: 'requesting_camera_permission' });
        const permissionResult = await requestCameraPermission();

        if (!isMounted.current) {
          return;
        }

        if (!permissionResult.granted) {
          setState({ status: 'camera_permission_denied' });
          return;
        }
      }

      if (isMounted.current) {
        setCameraReady(false);
        setCameraActive(true);
        setState({ status: 'camera_ready' });
      }
    } catch {
      if (isMounted.current) {
        setState({ status: 'camera_error' });
      }
    } finally {
      isOpeningCamera.current = false;
    }
  };

  const verifyFace = async () => {
    if (
      hasExited.current ||
      isProcessing.current ||
      hasContinued.current ||
      !cameraReady ||
      !cameraRef.current
    ) {
      return;
    }

    isProcessing.current = true;
    const requestId = activeRequest.current + 1;
    activeRequest.current = requestId;
    setState({ status: 'capturing' });

    try {
      const capture = await cameraRef.current.takePictureAsync({
        quality: 0.7,
      });

      if (!isMounted.current || activeRequest.current !== requestId) {
        return;
      }

      if (isReadinessCheck) {
        setCameraActive(false);
        setCameraReady(false);
      }
      setState({ status: 'processing' });

      const result = await faceVerificationService.verifyFace({
        sessionId,
        capture: {
          uri: capture.uri,
        },
      });

      if (isMounted.current && activeRequest.current === requestId) {
        setState(result);

        if (
          result.status === 'success' ||
          ('canRetry' in result && result.canRetry === false)
        ) {
          setCameraActive(false);
          setCameraReady(false);
        }
      }
    } catch {
      if (isMounted.current && activeRequest.current === requestId) {
        setState({ status: 'unexpected_error' });
      }
    } finally {
      if (activeRequest.current === requestId) {
        isProcessing.current = false;
      }
    }
  };

  const continueToResult = () => {
    if (
      hasExited.current ||
      state.status !== 'success' ||
      hasContinued.current
    ) {
      return;
    }

    hasContinued.current = true;
    onFaceVerified(sessionId);
  };

  const defaultContent =
    (isReadinessCheck ? readinessStatusContent[state.status] : undefined) ??
    statusContent[state.status];
  const content =
    !isReadinessCheck &&
    'canRetry' in state &&
    state.canRetry === false
      ? {
          ...defaultContent,
          message: 'No face verification attempts remain for this session.',
        }
      : defaultContent;
  const processing = state.status === 'processing';
  const showReadinessStage =
    isReadinessCheck && isVerificationOutcomeState(state.status);
  const livenessRequired = livenessMode === 'required';

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screenContent}>
      <ScreenHeader
        onBack={cancelAndExit}
        title={isReadinessCheck ? 'Face Readiness Check' : 'Face Verification'}
      />

      <View style={isReadinessCheck ? styles.readinessBody : undefined}>
        {isReadinessCheck ? null : (
          <AttendanceProgressSteps phase="face" />
        )}

        {livenessRequired ? (
          state.status === 'ready' ? (
            <LivenessCamera
              key={livenessSessionKey}
              onSuccess={(result) => {
                acceptLivenessResult(result, livenessSessionKey);
              }}
            />
          ) : (
            <VerificationStage content={content} processing={processing} />
          )
        ) : showReadinessStage ? (
          <VerificationStage content={content} processing={processing} />
        ) : (
          <FaceCameraPreview
            cameraActive={cameraActive}
            cameraRef={cameraRef}
            onCameraError={() => {
              setCameraActive(false);
              setCameraReady(false);
              setState({ status: 'camera_error' });
            }}
            onCameraReady={() => setCameraReady(true)}
            processing={state.status === 'capturing' || processing}
          />
        )}

        {livenessRequired || showReadinessStage ? null : (
          <StatusCard content={content} processing={processing} />
        )}

        {livenessRequired ? (
          state.status === 'success' ? (
            <View style={styles.action}>
              <AppButton
                accessibilityLabel={
                  isReadinessCheck
                    ? 'Return to dashboard'
                    : 'Continue to attendance progress'
                }
                onPress={continueToResult}
                title={isReadinessCheck ? 'Done' : 'Continue'}
              />
            </View>
          ) : canRetryWithFreshLiveness(state) ? (
            <View style={styles.action}>
              <AppButton
                accessibilityLabel="Retry face verification"
                onPress={retryRequiredLiveness}
                title="Try Again"
              />
            </View>
          ) : 'canRetry' in state && state.canRetry === false ? (
            <View style={styles.action}>
              <AppButton
                accessibilityLabel="Return to attendance session"
                onPress={cancelAndExit}
                title="Return to Session"
              />
            </View>
          ) : null
        ) : (
          <View style={styles.action}>
            <VerificationAction
              cameraReady={cameraReady}
              continueAccessibilityLabel={
                isReadinessCheck
                  ? 'Return to dashboard'
                  : 'Continue to attendance progress'
              }
              continueTitle={isReadinessCheck ? 'Done' : 'Continue'}
              onContinue={continueToResult}
              onExit={cancelAndExit}
              onOpenCamera={() => void openCamera()}
              onVerify={() => {
                if (isReadinessCheck && isVerificationFailureState(state.status)) {
                  void openCamera();
                  return;
                }

                void verifyFace();
              }}
              state={state}
            />
          </View>
        )}

        <View
          accessible
          accessibilityLabel={`Privacy notice. Your face is used only for ${
            isReadinessCheck ? 'readiness' : 'attendance'
          } verification and should not be stored unnecessarily.`}
          style={styles.privacyNotice}
        >
          <SymbolView
            name={{ ios: 'lock.fill', android: 'lock', web: 'lock' }}
            size={18}
            tintColor={lightColors.neutral}
          />
          <Text style={styles.privacyText}>
            Your face is used only for {isReadinessCheck ? 'readiness' : 'attendance'} verification and should not be stored unnecessarily.
          </Text>
        </View>
        </View>
    </ScreenContainer>
  );
}

function isVerificationOutcomeState(
  status: FaceVerificationUiState['status'],
): boolean {
  return (
    status === 'processing' ||
    status === 'success' ||
    isVerificationFailureState(status)
  );
}

function isVerificationFailureState(
  status: FaceVerificationUiState['status'],
): boolean {
  return (
    status === 'face_not_detected' ||
    status === 'multiple_faces' ||
    status === 'liveness_failure' ||
    status === 'service_unavailable' ||
    status === 'verification_failure' ||
    status === 'unexpected_error'
  );
}

function canRetryWithFreshLiveness(
  state: FaceVerificationUiState,
): boolean {
  if (
    !isVerificationFailureState(state.status) ||
    state.status === 'liveness_failure'
  ) {
    return false;
  }

  return !('canRetry' in state) || state.canRetry !== false;
}

const styles = StyleSheet.create({
  screenContent: {
    paddingBottom: spacing.xxl,
  },
  readinessBody: {
    flex: 1,
    justifyContent: 'center',
  },
  header: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  backButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.full,
    backgroundColor: lightColors.surface,
  },
  pressed: {
    opacity: 0.7,
  },
  screenTitle: {
    ...typography.screenTitle,
    flex: 1,
    color: lightColors.textPrimary,
  },
  cameraContainer: {
    height: 390,
    overflow: 'hidden',
    marginTop: spacing.xl,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.textPrimary,
  },
  cameraPlaceholder: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
    backgroundColor: lightColors.surface,
  },
  cameraPlaceholderTitle: {
    ...typography.cardTitle,
    marginTop: spacing.sm,
    color: lightColors.textPrimary,
  },
  cameraPlaceholderText: {
    ...typography.body,
    marginTop: spacing.xs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  verificationStage: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  verificationStageTitle: {
    ...typography.screenTitle,
    marginTop: spacing.lg,
    textAlign: 'center',
  },
  verificationStageMessage: {
    ...typography.body,
    maxWidth: 280,
    marginTop: spacing.sm,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  faceGuide: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  faceFrame: {
    width: 190,
    height: 240,
    borderWidth: 3,
    borderColor: lightColors.surface,
    borderRadius: radii.full,
  },
  cameraGuidance: {
    ...typography.supporting,
    marginTop: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.full,
    color: lightColors.surface,
    backgroundColor: 'rgba(0, 0, 0, 0.55)',
  },
  processingOverlay: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.45)',
  },
  statusCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginTop: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderRadius: radii.card,
  },
  infoStatus: {
    borderColor: lightColors.info,
    backgroundColor: lightColors.infoBackground,
  },
  successStatus: {
    borderColor: lightColors.success,
    backgroundColor: lightColors.successBackground,
  },
  errorStatus: {
    borderColor: lightColors.error,
    backgroundColor: lightColors.errorBackground,
  },
  statusCopy: {
    flex: 1,
  },
  statusTitle: {
    ...typography.cardTitle,
  },
  infoStatusTitle: {
    color: lightColors.info,
  },
  successStatusTitle: {
    color: lightColors.success,
  },
  errorStatusTitle: {
    color: lightColors.error,
  },
  statusMessage: {
    ...typography.body,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
  action: {
    marginTop: spacing.lg,
  },
  privacyNotice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginTop: spacing.md,
    padding: spacing.sm,
    borderRadius: radii.input,
    backgroundColor: lightColors.neutralBackground,
  },
  privacyText: {
    ...typography.supporting,
    flex: 1,
    color: lightColors.neutral,
  },
});

const statusContainerStyles = {
  info: styles.infoStatus,
  success: styles.successStatus,
  error: styles.errorStatus,
} as const;

const statusTitleStyles = {
  info: styles.infoStatusTitle,
  success: styles.successStatusTitle,
  error: styles.errorStatusTitle,
} as const;

const statusIconColors = {
  info: lightColors.info,
  success: lightColors.success,
  error: lightColors.error,
} as const;
