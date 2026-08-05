import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
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
  LocationStatusCard,
  type LocationStatusTone,
} from '../components/LocationStatusCard';
import type { LocationService } from '../services/locationService';

type LocationCheckScreenProps = {
  sessionId: string;
  locationService: LocationService;
  onBack: () => void;
  onLocationValidated: (sessionId: string) => void;
};

type LocationCheckUiState =
  | { status: 'permission_required' }
  | { status: 'checking' }
  | { status: 'inside_geofence' }
  | { status: 'outside_geofence' }
  | { status: 'permission_denied' }
  | { status: 'poor_accuracy' }
  | { status: 'stale_location' }
  | { status: 'unavailable' }
  | { status: 'unexpected_error' };

type LocationStatusContent = {
  icon: SymbolViewProps['name'];
  title: string;
  message: string;
  tone: LocationStatusTone;
};

const permissionRequiredState: LocationCheckUiState = {
  status: 'permission_required',
};

const statusContent: Record<
  LocationCheckUiState['status'],
  LocationStatusContent
> = {
  permission_required: {
    icon: {
      ios: 'location',
      android: 'location_on',
      web: 'location_on',
    },
    title: 'Location permission required',
    message:
      'Location access is required to confirm that you are inside the classroom.',
    tone: 'info',
  },
  checking: {
    icon: {
      ios: 'location',
      android: 'location_on',
      web: 'location_on',
    },
    title: 'Checking location…',
    message:
      'Confirming that you are inside the approved classroom area.',
    tone: 'info',
  },
  inside_geofence: {
    icon: {
      ios: 'checkmark.circle.fill',
      android: 'check_circle',
      web: 'check_circle',
    },
    title: 'Inside classroom area',
    message: 'Your classroom location has been verified.',
    tone: 'success',
  },
  outside_geofence: {
    icon: {
      ios: 'xmark.circle.fill',
      android: 'cancel',
      web: 'cancel',
    },
    title: 'Outside classroom area',
    message: 'Move inside the approved classroom area and check again.',
    tone: 'error',
  },
  permission_denied: {
    icon: {
      ios: 'location.slash',
      android: 'location_off',
      web: 'location_off',
    },
    title: 'Location permission denied',
    message:
      'Location permission is required to continue attendance verification.',
    tone: 'error',
  },
  poor_accuracy: {
    icon: {
      ios: 'exclamationmark.triangle.fill',
      android: 'warning',
      web: 'warning',
    },
    title: 'Location accuracy is too low',
    message:
      'Move closer to the classroom or wait a moment for a more accurate location.',
    tone: 'warning',
  },
  stale_location: {
    icon: {
      ios: 'clock.fill',
      android: 'schedule',
      web: 'schedule',
    },
    title: 'Location information is out of date',
    message:
      'We could not use the current location reading. Check your location again.',
    tone: 'warning',
  },
  unavailable: {
    icon: {
      ios: 'location.slash.fill',
      android: 'location_disabled',
      web: 'location_disabled',
    },
    title: 'Location is unavailable',
    message:
      'We could not obtain your current location. Check your location settings and try again.',
    tone: 'error',
  },
  unexpected_error: {
    icon: {
      ios: 'exclamationmark.circle.fill',
      android: 'error',
      web: 'error',
    },
    title: "We couldn't verify your location",
    message:
      'Check your connection and location settings, then try again.',
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
        Verify classroom location
      </Text>
    </View>
  );
}

function LocationStatusAction({
  sessionId,
  state,
  onLocationValidated,
  onValidateLocation,
}: {
  sessionId: string;
  state: Exclude<LocationCheckUiState, { status: 'checking' }>;
  onLocationValidated: (sessionId: string) => void;
  onValidateLocation: () => void;
}) {
  if (state.status === 'permission_required') {
    return (
      <AppButton
        accessibilityLabel="Allow location access and check classroom location"
        onPress={onValidateLocation}
        title="Continue"
      />
    );
  }

  if (state.status === 'inside_geofence') {
    return (
      <AppButton
        accessibilityLabel="Continue to face verification"
        onPress={() => onLocationValidated(sessionId)}
        title="Continue to Face Verification"
      />
    );
  }

  const retryTitle =
    state.status === 'outside_geofence'
      ? 'Check Location Again'
      : state.status === 'poor_accuracy' ||
          state.status === 'stale_location'
        ? 'Check Again'
        : 'Try Again';

  return (
    <AppButton
      accessibilityLabel="Retry classroom location validation"
      onPress={onValidateLocation}
      title={retryTitle}
    />
  );
}

export function LocationCheckScreen({
  sessionId,
  locationService,
  onBack,
  onLocationValidated,
}: LocationCheckScreenProps) {
  const [state, setState] = useState<LocationCheckUiState>(
    permissionRequiredState,
  );
  const requestSequence = useRef(0);
  const isChecking = useRef(false);
  const hasMounted = useRef(false);

  useEffect(() => {
    if (hasMounted.current) {
      setState(permissionRequiredState);
    } else {
      hasMounted.current = true;
    }

    return () => {
      requestSequence.current += 1;
      isChecking.current = false;
    };
  }, [locationService, sessionId]);

  const validateLocation = useCallback(async () => {
    if (isChecking.current) {
      return;
    }

    isChecking.current = true;
    const currentRequest = requestSequence.current + 1;
    requestSequence.current = currentRequest;
    setState({ status: 'checking' });

    try {
      const result = await locationService.validateLocation(sessionId);

      if (requestSequence.current === currentRequest) {
        setState(result);
      }
    } catch {
      if (requestSequence.current === currentRequest) {
        setState({ status: 'unexpected_error' });
      }
    } finally {
      if (requestSequence.current === currentRequest) {
        isChecking.current = false;
      }
    }
  }, [locationService, sessionId]);

  const content = statusContent[state.status];

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screenContent}>
      <ScreenHeader onBack={onBack} />

      <AttendanceProgressSteps phase="location" />

      <View style={styles.explanation}>
        <Text style={styles.explanationTitle}>
          Confirm your classroom location
        </Text>
        <Text style={styles.description}>
          Your location is used once to confirm that you are within the
          approved classroom area.
        </Text>
      </View>

      <LocationStatusCard
        action={
          state.status === 'checking' ? undefined : (
            <LocationStatusAction
              onLocationValidated={onLocationValidated}
              onValidateLocation={() => void validateLocation()}
              sessionId={sessionId}
              state={state}
            />
          )
        }
        icon={content.icon}
        loading={state.status === 'checking'}
        message={content.message}
        title={content.title}
        tone={content.tone}
      />

      <View
        accessible
        accessibilityLabel="Privacy notice. Location is checked only while completing this attendance verification."
        style={styles.privacyNotice}
      >
        <SymbolView
          name={{ ios: 'lock.fill', android: 'lock', web: 'lock' }}
          size={18}
          tintColor={lightColors.neutral}
        />
        <Text style={styles.privacyText}>
          Location is checked only while completing this attendance
          verification.
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
  explanation: {
    marginTop: spacing.xl,
  },
  explanationTitle: {
    ...typography.cardTitle,
    color: lightColors.textPrimary,
  },
  description: {
    ...typography.body,
    marginTop: spacing.xs,
    color: lightColors.textSecondary,
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
