import { SymbolView } from 'expo-symbols';
import { useRef } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';
import { AttendanceProgressSteps } from '../../attendance/components/AttendanceProgressSteps';
import { FaceVerificationGuidanceItem } from '../components/FaceVerificationGuidanceItem';

type FaceIntroductionScreenProps = {
  sessionId: string;
  onBack: () => void;
  onBeginVerification: (sessionId: string) => void;
};

export function FaceIntroductionScreen({
  sessionId,
  onBack,
  onBeginVerification,
}: FaceIntroductionScreenProps) {
  const hasBegunVerification = useRef(false);

  const beginVerification = () => {
    if (hasBegunVerification.current) {
      return;
    }

    hasBegunVerification.current = true;
    onBeginVerification(sessionId);
  };

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screenContent}>
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
          Face verification
        </Text>
      </View>

      <AttendanceProgressSteps phase="face" />

      <View style={styles.introduction}>
        <View style={styles.faceIcon}>
          <SymbolView
            name={{
              ios: 'face.smiling',
              android: 'face',
              web: 'face',
            }}
            size={48}
            tintColor={lightColors.primaryInteraction}
          />
        </View>
        <Text style={styles.introductionTitle}>
          Get ready for face verification
        </Text>
        <Text style={styles.introductionText}>
          We&apos;ll use the camera to verify your face and confirm liveness
          before recording attendance.
        </Text>
      </View>

      <View style={styles.guidanceCard}>
        <FaceVerificationGuidanceItem
          icon={{ ios: 'sun.max.fill', android: 'light_mode', web: 'light_mode' }}
          message="Face a light source and avoid strong backlighting or heavy shadows."
          title="Use good lighting"
        />
        <View style={styles.divider} />
        <FaceVerificationGuidanceItem
          icon={{ ios: 'viewfinder', android: 'center_focus_strong', web: 'center_focus_strong' }}
          message="Hold your device at eye level and keep your full face centered in the frame."
          title="Position your face"
        />
        <View style={styles.divider} />
        <FaceVerificationGuidanceItem
          icon={{ ios: 'person.fill', android: 'person', web: 'person' }}
          message="Stay still and look directly at the camera while verification is in progress."
          title="Keep still"
        />
      </View>

      <View style={styles.action}>
        <AppButton
          accessibilityLabel="Begin face verification"
          onPress={beginVerification}
          title="Begin Verification"
        />
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
  introduction: {
    alignItems: 'center',
    marginTop: spacing.xl,
  },
  faceIcon: {
    width: 96,
    height: 96,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryLight,
  },
  introductionTitle: {
    ...typography.sectionTitle,
    marginTop: spacing.md,
    textAlign: 'center',
    color: lightColors.textPrimary,
  },
  introductionText: {
    ...typography.body,
    maxWidth: 330,
    marginTop: spacing.xs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  guidanceCard: {
    gap: spacing.md,
    marginTop: spacing.xl,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: lightColors.border,
  },
  action: {
    marginTop: spacing.xl,
  },
});
