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
import type { FaceVerificationService } from '../services/faceVerificationService';
import type { FaceVerificationResult } from '../types/faceVerification';

type FaceVerificationScreenProps = {
  sessionId: string;
  faceVerificationService: FaceVerificationService;
  onBack: () => void;
  onFaceVerified: (sessionId: string) => void;
};

type FaceVerificationUiState =
  | { status: 'ready' }
  | { status: 'requesting_camera_permission' }
  | { status: 'camera_ready' }
  | { status: 'camera_permission_denied' }
  | { status: 'camera_error' }
  | { status: 'processing' }
  | Exclude<FaceVerificationResult, { status: 'success' }>
  | { status: 'unexpected_error' }
  | { status: 'success' };

type StatusTone = 'info' | 'success' | 'error';

type StatusContent = {
  icon: SymbolViewProps['name'];
  title: string;
  message: string;
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
  processing: {
    icon: {
      ios: 'face.smiling',
      android: 'face',
      web: 'face',
    },
    title: 'Verifying your face...',
    message: 'Please keep your face steady.',
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

function ScreenHeader({ onBack }: { onBack: () => void }) {
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
        Face Verification
      </Text>
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
        <Text style={styles.statusMessage}>{content.message}</Text>
      </View>
    </View>
  );
}

function VerificationAction({
  cameraReady,
  state,
  onContinue,
  onOpenCamera,
  onVerify,
}: {
  cameraReady: boolean;
  state: FaceVerificationUiState;
  onContinue: () => void;
  onOpenCamera: () => void;
  onVerify: () => void;
}) {
  if (state.status === 'success') {
    return (
      <AppButton
        accessibilityLabel="Continue to check-in result"
        onPress={onContinue}
        title="Continue"
      />
    );
  }

  if (
    state.status === 'requesting_camera_permission' ||
    state.status === 'processing'
  ) {
    const requestingPermission =
      state.status === 'requesting_camera_permission';

    return (
      <AppButton
        accessibilityLabel="Begin face verification"
        loading
        loadingTitle={
          requestingPermission
            ? 'Requesting Camera...'
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
  onBack,
  onFaceVerified,
}: FaceVerificationScreenProps) {
  const [permission, requestCameraPermission] = useCameraPermissions();
  const [state, setState] = useState<FaceVerificationUiState>({
    status: 'ready',
  });
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const cameraRef = useRef<CameraView>(null);
  const activeRequest = useRef(0);
  const isMounted = useRef(true);
  const isOpeningCamera = useRef(false);
  const isProcessing = useRef(false);
  const hasContinued = useRef(false);

  useEffect(() => {
    isMounted.current = true;

    return () => {
      isMounted.current = false;
      isOpeningCamera.current = false;
      isProcessing.current = false;
      activeRequest.current += 1;
    };
  }, []);

  const openCamera = async () => {
    if (
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
    setState({ status: 'processing' });

    try {
      const capture = await cameraRef.current.takePictureAsync({
        quality: 0.7,
      });
      const result = await faceVerificationService.verifyFace({
        sessionId,
        capture: {
          uri: capture.uri,
        },
      });

      if (isMounted.current && activeRequest.current === requestId) {
        setState(result);

        if (result.status === 'success') {
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
    if (state.status !== 'success' || hasContinued.current) {
      return;
    }

    hasContinued.current = true;
    onFaceVerified(sessionId);
  };

  const content = statusContent[state.status];
  const processing = state.status === 'processing';

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screenContent}>
      <ScreenHeader onBack={onBack} />

      <AttendanceProgressSteps phase="face" />

      <FaceCameraPreview
        cameraActive={cameraActive}
        cameraRef={cameraRef}
        onCameraError={() => {
          setCameraActive(false);
          setCameraReady(false);
          setState({ status: 'camera_error' });
        }}
        onCameraReady={() => setCameraReady(true)}
        processing={processing}
      />

      <StatusCard content={content} processing={processing} />

      <View style={styles.action}>
        <VerificationAction
          cameraReady={cameraReady}
          onContinue={continueToResult}
          onOpenCamera={() => void openCamera()}
          onVerify={() => void verifyFace()}
          state={state}
        />
      </View>

      <View
        accessible
        accessibilityLabel="Privacy notice. Your face is used only for attendance verification and should not be stored unnecessarily."
        style={styles.privacyNotice}
      >
        <SymbolView
          name={{ ios: 'lock.fill', android: 'lock', web: 'lock' }}
          size={18}
          tintColor={lightColors.neutral}
        />
        <Text style={styles.privacyText}>
          Your face is used only for attendance verification and should not be
          stored unnecessarily.
        </Text>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  screenContent: {
    paddingBottom: spacing.xxl,
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
