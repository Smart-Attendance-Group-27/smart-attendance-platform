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

type QrScannerScreenProps = {
  sessionId: string;
  onBack: () => void;
  onQrScanned?: (result: { sessionId: string; qrValue: string }) => void;
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
  onBack,
  onQrScanned,
}: QrScannerScreenProps) {
  const [permission, requestPermission] = useCameraPermissions();

  const [scanned, setScanned] = useState(false);
  const [scannedQrValue, setScannedQrValue] = useState<string | null>(null);

  function handleQrScanned(result: BarcodeScanningResult) {
    if (scanned) {
      return;
    }

    const qrValue = result.data.trim();

    if (!qrValue) {
      return;
    }

    setScanned(true);
    setScannedQrValue(qrValue);
    onQrScanned?.({ sessionId, qrValue });
  }

  function scanAgain() {
    setScannedQrValue(null);
    setScanned(false);
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
          Point your camera at the QR displayed in class. The decoded value is
          kept only in memory for this test screen.
        </Text>
      </View>

      <View style={styles.cameraContainer}>
        {!scanned && (
          <CameraView
            style={StyleSheet.absoluteFill}
            barcodeScannerSettings={{
              barcodeTypes: ['qr'],
            }}
            facing="back"
            onBarcodeScanned={handleQrScanned}
          />
        )}

        <View pointerEvents="none" style={styles.scanFrame} />
      </View>

      {scannedQrValue ? (
        <View style={styles.successBox}>
          <Text style={styles.successTitle}>QR captured successfully</Text>

          <Text style={styles.supportText}>
            The QR value was decoded and is ready for verification.
          </Text>

          <Text
            accessibilityLabel="Decoded QR value"
            numberOfLines={3}
            style={styles.qrPreview}
          >
            {scannedQrValue}
          </Text>

          <AppButton
            accessibilityLabel="Scan another QR code"
            onPress={scanAgain}
            title="Scan Again"
            variant="secondary"
          />
        </View>
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
  successBox: {
    marginTop: spacing.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.success,
    borderRadius: radii.card,
    backgroundColor: lightColors.successBackground,
    gap: spacing.sm,
  },
  successTitle: {
    ...typography.cardTitle,
    color: lightColors.success,
  },
  qrPreview: {
    ...typography.caption,
    padding: spacing.sm,
    borderRadius: radii.input,
    backgroundColor: lightColors.surface,
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
