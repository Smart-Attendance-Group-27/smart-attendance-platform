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
import type { LocationValidationResult } from '../types/locationValidation';

type LocationCheckScreenProps = {
  sessionId: string;
  locationService: LocationService;
  onBack: () => void;
  onLocationValidated: (sessionId: string) => void;
};

type LocationCheckUiState =
  | { status: 'permission_required' }
  | { status: 'checking' }
  | LocationValidationResult
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
    title: 'Checking location...',
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
    message:
      'This location attempt is outside the approved classroom area.',
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
  services_disabled: {
    icon: {
      ios: 'location.slash',
      android: 'location_off',
      web: 'location_off',
    },
    title: 'Location services are turned off',
    message:
      'Turn on Location Services for your phone, then check again.',
    tone: 'warning',
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
  retry_required: {
    icon: {
      ios: 'scope',
      android: 'my_location',
      web: 'my_location',
    },
    title: 'A clearer location is needed',
    message:
      'Your location overlaps the classroom boundary. Wait a moment, then check again.',
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
  mock_location_detected: {
    icon: {
      ios: 'exclamationmark.shield.fill',
      android: 'gpp_bad',
      web: 'gpp_bad',
    },
    title: 'Mock location detected',
    message:
      'Attendance verification cannot continue with a simulated location.',
    tone: 'error',
  },
  session_unavailable: {
    icon: {
      ios: 'clock.badge.xmark.fill',
      android: 'event_busy',
      web: 'event_busy',
    },
    title: 'Attendance session unavailable',
    message:
      'This session is closed, inactive, or no longer accepting location attempts.',
    tone: 'error',
  },
  attempt_limit_reached: {
    icon: {
      ios: 'exclamationmark.octagon.fill',
      android: 'block',
      web: 'block',
    },
    title: 'Location attempt limit reached',
    message:
      'No more location attempts are available for this attendance check-in.',
    tone: 'error',
  },
  unauthenticated: {
    icon: {
      ios: 'person.crop.circle.badge.exclamationmark',
      android: 'person_off',
      web: 'person_off',
    },
    title: 'Sign-in required',
    message:
      'Your sign-in session has expired. Sign in again before checking attendance.',
    tone: 'error',
  },
  forbidden: {
    icon: {
      ios: 'hand.raised.fill',
      android: 'block',
      web: 'block',
    },
    title: 'Attendance access denied',
    message:
      'You are not eligible to check in to this attendance session.',
    tone: 'error',
  },
  invalid_request: {
    icon: {
      ios: 'exclamationmark.triangle.fill',
      android: 'warning',
      web: 'warning',
    },
    title: 'Location reading was not accepted',
    message:
      'Capture a new location reading and try the verification again.',
    tone: 'warning',
  },
  network_error: {
    icon: {
      ios: 'wifi.exclamationmark',
      android: 'wifi_off',
      web: 'wifi_off',
    },
    title: 'Cannot reach UniAttend',
    message:
      'Check your connection to the attendance server, then try again.',
    tone: 'error',
  },
  server_error: {
    icon: {
      ios: 'exclamationmark.circle.fill',
      android: 'error',
      web: 'error',
    },
    title: 'Location verification is unavailable',
    message:
      'The attendance server could not verify your location. Try again shortly.',
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

  if (
    state.status === 'outside_geofence' ||
    state.status === 'mock_location_detected' ||
    state.status === 'session_unavailable' ||
    state.status === 'attempt_limit_reached' ||
    state.status === 'unauthenticated' ||
    state.status === 'forbidden'
  ) {
    return null;
  }

  const retryTitle =
    state.status === 'poor_accuracy' ||
    state.status === 'retry_required' ||
    state.status === 'stale_location' ||
    state.status === 'services_disabled' ||
    state.status === 'invalid_request'
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
