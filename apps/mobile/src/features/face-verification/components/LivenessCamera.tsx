import { CameraView, useCameraPermissions } from 'expo-camera';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  ActivityIndicator,
  AppState,
  type AppStateStatus,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AppButton } from '../../../components/ui';
import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';
import {
  createExpoCameraCaptureSource,
  LIVENESS_CAMERA_FACING,
  type LivenessCapturedPhoto,
  type ExpoCameraCaptureSource,
} from '../liveness/expoCameraCaptureSource';
import {
  createLivenessSessionController,
  type LivenessSessionController,
  type LivenessSessionSnapshot,
} from '../liveness/livenessSessionController';
import type { LivenessEvidence } from '../liveness/livenessEvidence';
import type { LivenessChallenge } from '../liveness/livenessTypes';

type LivenessControllerFactory = (
  captureSource: ExpoCameraCaptureSource,
) => LivenessSessionController;

type LivenessCameraProps = {
  readonly controllerFactory?: LivenessControllerFactory;
  readonly onCancel?: () => void;
  readonly onSuccess?: (result: LivenessCameraResult) => void;
};

export type LivenessCameraResult = {
  readonly photo: LivenessCapturedPhoto;
  readonly livenessEvidence: LivenessEvidence;
};

const defaultControllerFactory: LivenessControllerFactory = (captureSource) =>
  createLivenessSessionController({
    captureSource,
    challengePreparationMs: 5_000,
  });

const EMPTY_SNAPSHOT: LivenessSessionSnapshot = {
  status: 'idle',
  sessionState: null,
  activeChallenge: null,
  completedChallengeCount: 0,
  challengeCount: 0,
  failure: null,
  timeoutReason: null,
  finalPhoto: null,
  livenessEvidence: null,
  preparingChallenge: false,
};

const EMPTY_CONTROLLER: LivenessSessionController = {
  cancel: () => undefined,
  claimFinalPhoto: () => null,
  dispose: () => undefined,
  getSnapshot: () => EMPTY_SNAPSHOT,
  retryCurrentChallenge: () => undefined,
  restart: () => undefined,
  start: () => undefined,
  subscribe: () => () => undefined,
};

const CHALLENGE_INSTRUCTIONS: Record<LivenessChallenge, string> = {
  turn_left: 'Turn your head left',
  turn_right: 'Turn your head right',
  eyes_closed_hold: 'Close both eyes and hold',
};

export function LivenessCamera({
  controllerFactory = defaultControllerFactory,
  onCancel,
  onSuccess,
}: LivenessCameraProps) {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const successReportedRef = useRef(false);
  const restartWhenCameraReadyRef = useRef(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraKey, setCameraKey] = useState(0);
  const [requestingPermission, setRequestingPermission] = useState(false);
  const [appState, setAppState] = useState<AppStateStatus>(
    AppState.currentState ?? 'active',
  );
  const [controller, setController] = useState<
    LivenessSessionController | null
  >(null);
  const activeController = controller ?? EMPTY_CONTROLLER;
  const snapshot = useSyncExternalStore(
    activeController.subscribe,
    activeController.getSnapshot,
    activeController.getSnapshot,
  );

  useEffect(() => {
    const captureSource = createExpoCameraCaptureSource({
      getCamera: () => cameraRef.current,
    });
    const nextController = controllerFactory(captureSource);
    setController(nextController);

    return () => nextController.dispose();
  }, [controllerFactory]);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState) => {
      setAppState(nextState);
      if (nextState === 'background' || nextState === 'inactive') {
        controller?.cancel();
      }
    });

    return () => subscription.remove();
  }, [controller]);

  useEffect(() => {
    if (
      permission?.granted &&
      appState !== 'background' &&
      appState !== 'inactive' &&
      cameraReady &&
      !cameraError &&
      controller
    ) {
      if (restartWhenCameraReadyRef.current) {
        restartWhenCameraReadyRef.current = false;
        controller.restart();
      } else if (snapshot.status === 'idle') {
        controller.start();
      }
    }
  }, [
    cameraError,
    cameraReady,
    controller,
    appState,
    permission?.granted,
    snapshot.status,
  ]);

  useEffect(() => {
    if (
      snapshot.status === 'passed' &&
      snapshot.sessionState &&
      snapshot.finalPhoto &&
      snapshot.livenessEvidence &&
      controller &&
      onSuccess &&
      !successReportedRef.current
    ) {
      const finalPhoto = controller.claimFinalPhoto();
      if (finalPhoto) {
        successReportedRef.current = true;
        onSuccess({
          photo: finalPhoto,
          livenessEvidence: snapshot.livenessEvidence,
        });
      }
    }
  }, [
    controller,
    onSuccess,
    snapshot.finalPhoto,
    snapshot.livenessEvidence,
    snapshot.sessionState,
    snapshot.status,
  ]);

  const askForPermission = async () => {
    if (requestingPermission) return;
    setRequestingPermission(true);
    try {
      await requestPermission();
    } finally {
      setRequestingPermission(false);
    }
  };

  const restart = () => {
    successReportedRef.current = false;
    setCameraError(null);
    if (!cameraReady) {
      restartWhenCameraReadyRef.current = true;
      setCameraKey((key) => key + 1);
      return;
    }
    controller?.retryCurrentChallenge();
  };

  const cancel = () => {
    controller?.cancel();
    onCancel?.();
  };

  const handleCameraReady = useCallback(() => {
    setCameraError(null);
    setCameraReady(true);
  }, []);

  const handleCameraMountError = useCallback(
    (event: { message: string }) => {
      setCameraReady(false);
      restartWhenCameraReadyRef.current = false;
      setCameraError(event.message || 'The front camera could not start.');
      controller?.cancel();
    },
    [controller],
  );

  if (!permission) {
    return (
      <StatusOnlyView
        message="Checking camera permission..."
        title="Preparing liveness check"
      />
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.permissionContainer}>
        <Text style={styles.statusTitle}>Camera permission required</Text>
        <Text style={styles.statusMessage}>
          Allow camera access to complete the liveness check.
        </Text>
        <AppButton
          loading={requestingPermission}
          loadingTitle="Requesting Camera..."
          onPress={() => void askForPermission()}
          title="Allow Camera Access"
        />
      </View>
    );
  }

  const content = getStatusContent(snapshot, cameraReady, cameraError);
  const canRestart =
    cameraError !== null ||
    (cameraReady &&
      (snapshot.status === 'failed' ||
      snapshot.status === 'timed_out' ||
      snapshot.status === 'cancelled'));

  return (
    <View style={styles.container}>
      <View
        accessible
        accessibilityLabel="Liveness front camera preview"
        accessibilityState={{ busy: snapshot.status === 'running' }}
        style={styles.cameraContainer}
      >
        <CameraView
          facing={LIVENESS_CAMERA_FACING}
          key={cameraKey}
          mirror
          mode="picture"
          onCameraReady={handleCameraReady}
          onMountError={handleCameraMountError}
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
        />
        <View pointerEvents="none" style={styles.faceGuide}>
          <View style={styles.faceFrame} />
        </View>
      </View>

      <View
        accessibilityLabel={
          snapshot.status === 'running' ? 'Liveness processing' : undefined
        }
        accessibilityState={{ busy: snapshot.status === 'running' }}
        style={styles.statusCard}
      >
        {snapshot.status === 'running' ? (
          <ActivityIndicator
            color={lightColors.primaryInteraction}
            size="small"
          />
        ) : null}
        <View style={styles.statusCopy}>
          <Text style={styles.progress}>{content.progress}</Text>
          <Text style={styles.statusTitle}>{content.title}</Text>
          <Text style={styles.statusMessage}>{content.message}</Text>
        </View>
      </View>

      {canRestart ? (
        <AppButton onPress={restart} title="Try Again" />
      ) : null}
      {snapshot.status === 'running' ? (
        <AppButton onPress={cancel} title="Cancel" variant="secondary" />
      ) : null}
    </View>
  );
}

function getStatusContent(
  snapshot: LivenessSessionSnapshot,
  cameraReady: boolean,
  cameraError: string | null,
): { message: string; progress: string; title: string } {
  if (cameraError) {
    return {
      progress: 'Camera unavailable',
      title: 'Camera could not start',
      message: cameraError,
    };
  }

  if (!cameraReady || snapshot.status === 'idle') {
    return {
      progress: 'Preparing camera',
      title: 'Hold your phone steady',
      message: 'Keep your face inside the guide while the camera starts.',
    };
  }

  if (snapshot.status === 'running') {
    if (snapshot.activeChallenge) {
      return {
        progress: `Challenge ${snapshot.completedChallengeCount + 1} of ${snapshot.challengeCount}`,
        title: CHALLENGE_INSTRUCTIONS[snapshot.activeChallenge],
        message: snapshot.preparingChallenge
          ? snapshot.completedChallengeCount > 0
            ? 'Previous challenge complete. Get ready—the next check starts in 5 seconds.'
            : 'Get into position. Capturing starts in 5 seconds.'
          : snapshot.activeChallenge === 'eyes_closed_hold'
            ? 'Keep both eyes fully closed until this challenge is confirmed.'
            : 'Keep your face visible while we check your movement.',
      };
    }

    return {
      progress: 'Final check',
      title: snapshot.preparingChallenge
        ? 'Challenges complete'
        : 'Look straight at the camera',
      message: snapshot.preparingChallenge
        ? 'Face forward now. Your final photo will be captured in 5 seconds.'
        : 'Hold still briefly while we confirm your frontal position.',
    };
  }

  if (snapshot.status === 'passed') {
    return {
      progress: 'Complete',
      title: 'Liveness check passed',
      message: 'Your movements were confirmed successfully.',
    };
  }

  if (snapshot.status === 'timed_out') {
    return {
      progress: 'Time expired',
      title: 'Liveness check timed out',
      message: 'Complete each movement promptly and try again.',
    };
  }

  if (snapshot.status === 'cancelled') {
    return {
      progress: 'Cancelled',
      title: 'Liveness check cancelled',
      message: 'Start again when you are ready.',
    };
  }

  return {
    progress: 'Try again',
    title: 'Liveness check could not continue',
    message: getFailureMessage(snapshot),
  };
}

function getFailureMessage(snapshot: LivenessSessionSnapshot): string {
  if (snapshot.failure?.kind === 'capture_source') {
    const messages = {
      unsupported_platform: 'Liveness capture is currently available on Android only.',
      camera_unavailable: 'Wait for the front camera to become ready, then try again.',
      capture_in_progress: 'Wait for the current camera check to finish, then try again.',
      capture_failed: 'The camera could not capture an image. Please try again.',
      detection_failed: 'Your face could not be analyzed locally. Please try again.',
      invalid_capture: 'The camera returned an unusable image. Please try again.',
      cleanup_failed: 'A temporary camera image could not be cleared. Please try again.',
    } as const;
    return messages[snapshot.failure.error.code];
  }

  const reason = snapshot.failure?.kind === 'observation'
    ? snapshot.failure.reason
    : null;
  const messages = {
    no_face: 'Keep your face fully visible inside the guide and try again.',
    multiple_faces: 'Make sure only one person is visible and try again.',
    face_too_small: 'Move closer to the camera and try again.',
    yaw_unavailable: 'Keep your full face visible and try the movement again.',
    eye_probabilities_unavailable: 'Keep both eyes clearly visible and try again.',
    invalid_observation: 'The camera reading was invalid. Please try again.',
    tracking_id_changed: 'The detected face changed during the check. Please try again.',
  } as const;

  return reason
    ? messages[reason]
    : 'Check your position and try the liveness check again.';
}

function StatusOnlyView({
  message,
  title,
}: {
  readonly message: string;
  readonly title: string;
}) {
  return (
    <View style={styles.permissionContainer}>
      <Text style={styles.statusTitle}>{title}</Text>
      <Text style={styles.statusMessage}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.md,
  },
  permissionContainer: {
    gap: spacing.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
  },
  cameraContainer: {
    height: 390,
    overflow: 'hidden',
    borderRadius: radii.card,
    backgroundColor: lightColors.textPrimary,
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
  statusCard: {
    minHeight: 112,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
  },
  statusCopy: {
    flex: 1,
  },
  progress: {
    ...typography.supporting,
    color: lightColors.primaryInteraction,
  },
  statusTitle: {
    ...typography.cardTitle,
    marginTop: spacing.xxs,
    color: lightColors.textPrimary,
  },
  statusMessage: {
    ...typography.body,
    marginTop: spacing.xs,
    color: lightColors.textSecondary,
  },
});
