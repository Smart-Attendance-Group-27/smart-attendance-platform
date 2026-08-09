import {
  CameraView,
  type BarcodeScanningResult,
  useCameraPermissions,
} from 'expo-camera';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, radii, spacing, typography } from '../../../theme';
import type {
  QrVerificationResult,
  QrVerificationStatus,
} from '../types/qrVerification';
import type { QrVerificationService } from '../services/qrVerificationService';
import { parseScannedQrPayload } from '../utils/parseScannedQrPayload';

type QrScannerScreenProps = {
  sessionId: string;
  qrSessionId?: string;
  qrVerificationService: QrVerificationService;
  onBack: () => void;
  onQrVerified?: (result: QrVerificationResult) => void;
};

type QrScannerUiState =
  | { status: 'scanning' }
  | { status: 'verifying' }
  | { status: QrVerificationStatus; verifiedAt: string }
  | { status: 'missing_qr_session' }
  | { status: 'verification_error' };

type VerificationContent = {
  title: string;
  message: string;
  tone: 'success' | 'error' | 'warning' | 'neutral';
};

const verificationContent: Record<
  Exclude<QrScannerUiState['status'], 'scanning' | 'verifying'>,
  VerificationContent
> = {
  accepted: {
    title: 'QR verified',
    message: 'This QR code is valid for the active attendance session.',
    tone: 'success',
  },
  invalid: {
    title: 'Invalid QR code',
    message: 'This QR code does not match the active attendance QR session.',
    tone: 'error',
  },
  expired: {
    title: 'QR code expired',
    message: 'Ask the lecturer to generate a fresh QR code, then scan again.',
    tone: 'warning',
  },
  closed: {
    title: 'QR session closed',
    message:
      'This attendance QR session is no longer accepting verification.',
    tone: 'neutral',
  },
  missing_qr_session: {
    title: 'QR session ID missing',
    message:
      'This QR code could not be verified because it did not include the QR session ID.',
    tone: 'error',
  },
  verification_error: {
    title: "We couldn't verify the QR",
    message:
      'Check your connection to the backend service, then scan the QR again.',
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
        Scan attendance QR
      </Text>
    </View>
  );
}

export function QrScannerScreen({
  sessionId,
  qrSessionId,
  qrVerificationService,
  onBack,
  onQrVerified,
}: QrScannerScreenProps) {
  const [permission, requestPermission] = useCameraPermissions();

  const [state, setState] = useState<QrScannerUiState>({
    status: 'scanning',
  });

  async function handleQrScanned(result: BarcodeScanningResult) {
    if (state.status !== 'scanning') {
      return;
    }

    const scannedPayload = parseScannedQrPayload(result.data);

    if (!scannedPayload.qrValue) {
      return;
    }

    const targetQrSessionId = scannedPayload.qrSessionId ?? qrSessionId;

    if (!targetQrSessionId) {
      setState({ status: 'missing_qr_session' });
      return;
    }

    setState({ status: 'verifying' });

    try {
      const verificationResult =
        await qrVerificationService.verifyQrSession({
          qrSessionId: targetQrSessionId,
          qrValue: scannedPayload.qrValue,
        });

      setState({
        status: verificationResult.status,
        verifiedAt: verificationResult.verifiedAt,
      });
      onQrVerified?.(verificationResult);
    } catch {
      setState({ status: 'verification_error' });
    }
  }

  function scanAgain() {
    setState({ status: 'scanning' });
  }

  if (!permission) {
    return (
      <ScreenContainer contentContainerStyle={styles.centerContent}>
        <ActivityIndicator
          accessibilityLabel="Checking camera permission"
          accessibilityRole="progressbar"
          color={lightColors.primaryInteraction}
          size="large"
        />
        <Text style={styles.supportText}>
          Checking camera permission...
        </Text>
      </ScreenContainer>
    );
  }

  if (!permission.granted) {
    return (
      <ScreenContainer contentContainerStyle={styles.centerContent}>
        <ScreenHeader onBack={onBack} />
        <View style={styles.permissionCard}>
          <View style={styles.permissionIcon}>
            <SymbolView
              name={{
                ios: 'camera.fill',
                android: 'photo_camera',
                web: 'photo_camera',
              }}
              size={30}
              tintColor={lightColors.primaryInteraction}
            />
          </View>
          <Text style={styles.title}>Camera permission required</Text>

          <Text style={styles.supportText}>
            UniAttend needs camera access to scan the lecturer&apos;s QR code.
          </Text>
        </View>

        <AppButton
          accessibilityLabel="Allow camera access"
          onPress={requestPermission}
          title="Allow Camera Access"
        />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screenContent}>
      <ScreenHeader onBack={onBack} />

      <View style={styles.explanation}>
        <Text style={styles.title}>Scan the lecturer&apos;s QR code</Text>
        <Text style={styles.supportText}>
          Point your camera at the QR displayed in class. UniAttend verifies it
          with the attendance backend without showing the raw QR value.
        </Text>
      </View>

      <View style={styles.cameraContainer}>
        {state.status === 'scanning' && (
          <CameraView
            style={StyleSheet.absoluteFill}
            barcodeScannerSettings={{
              barcodeTypes: ['qr'],
            }}
            facing="back"
            onBarcodeScanned={(result) => {
              void handleQrScanned(result);
            }}
          />
        )}

        <View pointerEvents="none" style={styles.scanFrame} />
      </View>

      {state.status === 'verifying' ? (
        <View style={styles.waitingCard}>
          <ActivityIndicator
            accessibilityLabel="Verifying QR code"
            accessibilityRole="progressbar"
            color={lightColors.primaryInteraction}
          />
          <Text style={styles.waitingText}>Verifying QR code...</Text>
        </View>
      ) : state.status !== 'scanning' ? (
        <VerificationResultCard state={state} onScanAgain={scanAgain} />
      ) : (
        <View style={styles.waitingCard}>
          <ActivityIndicator
            accessibilityLabel="Waiting for QR code"
            accessibilityRole="progressbar"
            color={lightColors.primaryInteraction}
          />
          <Text style={styles.waitingText}>Waiting for QR code...</Text>
        </View>
      )}
    </ScreenContainer>
  );
}

function VerificationResultCard({
  state,
  onScanAgain,
}: {
  state: Exclude<QrScannerUiState, { status: 'scanning' | 'verifying' }>;
  onScanAgain: () => void;
}) {
  const content = verificationContent[state.status];
  const verifiedAt =
    'verifiedAt' in state
      ? new Intl.DateTimeFormat(undefined, {
          dateStyle: 'medium',
          timeStyle: 'short',
        }).format(new Date(state.verifiedAt))
      : null;

  return (
    <View style={[styles.resultBox, resultToneStyles[content.tone]]}>
      <Text style={[styles.resultTitle, resultTitleToneStyles[content.tone]]}>
        {content.title}
      </Text>
      <Text style={styles.supportText}>{content.message}</Text>

      {verifiedAt ? (
        <Text style={styles.verifiedAtText}>Verified at {verifiedAt}</Text>
      ) : null}

      <AppButton
        accessibilityLabel="Scan another QR code"
        onPress={onScanAgain}
        title="Scan Again"
        variant="secondary"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screenContent: {
    paddingBottom: spacing.xxl,
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    gap: spacing.lg,
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
  explanation: {
    marginTop: spacing.xl,
  },
  title: {
    ...typography.cardTitle,
    color: lightColors.textPrimary,
  },
  supportText: {
    ...typography.body,
    marginTop: spacing.xs,
    color: lightColors.textSecondary,
  },
  cameraContainer: {
    height: 420,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    marginTop: spacing.lg,
    backgroundColor: lightColors.textPrimary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scanFrame: {
    width: 230,
    height: 230,
    borderWidth: 3,
    borderColor: lightColors.accent,
    borderRadius: radii.card,
  },
  resultBox: {
    marginTop: spacing.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderRadius: radii.card,
    gap: spacing.sm,
  },
  resultSuccess: {
    borderColor: lightColors.success,
    backgroundColor: lightColors.successBackground,
  },
  resultError: {
    borderColor: lightColors.error,
    backgroundColor: lightColors.errorBackground,
  },
  resultWarning: {
    borderColor: lightColors.warning,
    backgroundColor: lightColors.warningBackground,
  },
  resultNeutral: {
    borderColor: lightColors.border,
    backgroundColor: lightColors.neutralBackground,
  },
  resultTitle: {
    ...typography.cardTitle,
  },
  resultTitleSuccess: {
    color: lightColors.success,
  },
  resultTitleError: {
    color: lightColors.error,
  },
  resultTitleWarning: {
    color: lightColors.warning,
  },
  resultTitleNeutral: {
    color: lightColors.neutral,
  },
  verifiedAtText: {
    ...typography.caption,
    color: lightColors.textSecondary,
  },
  waitingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
    padding: spacing.sm,
    borderRadius: radii.input,
    backgroundColor: lightColors.neutralBackground,
  },
  waitingText: {
    ...typography.supporting,
    color: lightColors.neutral,
  },
  permissionCard: {
    alignItems: 'center',
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
  },
  permissionIcon: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryLight,
  },
});

const resultToneStyles = {
  success: styles.resultSuccess,
  error: styles.resultError,
  warning: styles.resultWarning,
  neutral: styles.resultNeutral,
} as const;

const resultTitleToneStyles = {
  success: styles.resultTitleSuccess,
  error: styles.resultTitleError,
  warning: styles.resultTitleWarning,
  neutral: styles.resultTitleNeutral,
} as const;
