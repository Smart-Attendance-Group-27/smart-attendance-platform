import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, radii, spacing, typography } from '../../../theme';
import { AttendanceProgressSteps } from '../components/AttendanceProgressSteps';
import { AttendanceSessionCard } from '../components/AttendanceSessionCard';
import type { AttendanceService } from '../services/attendanceService';
import type { AttendanceSession } from '../types/attendanceSession';
import {
  formatAttendanceSession,
  formatAttendanceTime,
} from '../utils/formatAttendanceSession';

type AttendanceSessionDetailsScreenProps = {
  sessionId: string;
  attendanceService: AttendanceService;
  onBack: () => void;
  onStartCheckIn: () => void;
};

type AttendanceSessionDetailsState =
  | { status: 'loading' }
  | { status: 'ready'; session: AttendanceSession }
  | { status: 'unavailable' }
  | { status: 'error' };

type StateMessageProps = {
  icon: SymbolViewProps['name'];
  title: string;
  message: string;
  children?: React.ReactNode;
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
      <Text accessibilityRole="header" style={styles.title}>
        Attendance session
      </Text>
    </View>
  );
}

function StateMessage({
  icon,
  title,
  message,
  children,
}: StateMessageProps) {
  return (
    <View style={styles.stateContainer}>
      <View style={styles.stateIcon}>
        <SymbolView
          name={icon}
          size={30}
          tintColor={lightColors.neutral}
        />
      </View>
      <Text accessibilityRole="header" style={styles.stateTitle}>
        {title}
      </Text>
      <Text style={styles.stateMessage}>{message}</Text>
      {children}
    </View>
  );
}

export function AttendanceSessionDetailsScreen({
  sessionId,
  attendanceService,
  onBack,
  onStartCheckIn,
}: AttendanceSessionDetailsScreenProps) {
  const [state, setState] = useState<AttendanceSessionDetailsState>({
    status: 'loading',
  });
  const [requestNumber, setRequestNumber] = useState(0);

  useEffect(() => {
    let isMounted = true;

    attendanceService
      .getAttendanceSession(sessionId)
      .then((result) => {
        if (!isMounted) {
          return;
        }

        if (result.status === 'available') {
          setState({ status: 'ready', session: result.session });
          return;
        }

        setState({ status: 'unavailable' });
      })
      .catch(() => {
        if (isMounted) {
          setState({ status: 'error' });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [attendanceService, requestNumber, sessionId]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setRequestNumber((currentRequest) => currentRequest + 1);
  }, []);

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screenContent}>
      <ScreenHeader onBack={onBack} />

      {state.status === 'loading' ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator
            accessible
            accessibilityLabel="Loading attendance session"
            accessibilityRole="progressbar"
            accessibilityState={{ busy: true }}
            color={lightColors.primaryInteraction}
            size="large"
          />
          <Text style={styles.loadingText}>Loading session details…</Text>
        </View>
      ) : null}

      {state.status === 'unavailable' ? (
        <StateMessage
          icon={{
            ios: 'calendar.badge.exclamationmark',
            android: 'event_busy',
            web: 'event_busy',
          }}
          message="This attendance session could not be found or is no longer available."
          title="Session unavailable"
        />
      ) : null}

      {state.status === 'error' ? (
        <StateMessage
          icon={{
            ios: 'exclamationmark.triangle',
            android: 'warning',
            web: 'warning',
          }}
          message="Check your connection and try again."
          title="We couldn't load this session"
        >
          <View style={styles.retryButton}>
            <AppButton
              accessibilityLabel="Retry loading attendance session"
              onPress={retry}
              title="Retry"
            />
          </View>
        </StateMessage>
      ) : null}

      {state.status === 'ready' ? (
        <SessionContent
          onStartCheckIn={onStartCheckIn}
          session={state.session}
        />
      ) : null}
    </ScreenContainer>
  );
}

function SessionContent({
  session,
  onStartCheckIn,
}: {
  session: AttendanceSession;
  onStartCheckIn: () => void;
}) {
  const formattedSession = formatAttendanceSession(session);
  const isOpen = session.checkInStatus === 'open';
  const isScheduled = session.checkInStatus === 'not_started';

  return (
    <View style={styles.readyContent}>
      <AttendanceSessionCard
        formattedSession={formattedSession}
        session={session}
      />
      <AttendanceProgressSteps />

      {!isOpen ? (
        <View style={styles.readOnlyNotice}>
          <SymbolView
            name={
              isScheduled
                ? { ios: 'clock', android: 'schedule', web: 'schedule' }
                : { ios: 'lock', android: 'lock', web: 'lock' }
            }
            size={20}
            tintColor={lightColors.neutral}
          />
          <Text style={styles.readOnlyText}>
            {isScheduled
              ? `Attendance opens at ${formatAttendanceTime(session.checkInOpensAt)}. You can start check-in once the session begins.`
              : 'This attendance session has ended. Details are read-only.'}
          </Text>
        </View>
      ) : null}

      {isOpen ? (
        <View style={styles.action}>
          <AppButton
            accessibilityLabel="Start attendance check-in"
            onPress={onStartCheckIn}
            title="Start Check-In"
          />
        </View>
      ) : null}

      {isScheduled ? (
        <View style={styles.action}>
          <AppButton
            accessibilityLabel="Start attendance check-in"
            disabled
            title={`Attendance opens at ${formatAttendanceTime(session.checkInOpensAt)}`}
          />
        </View>
      ) : null}
    </View>
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
    marginBottom: spacing.lg,
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
  title: {
    ...typography.screenTitle,
    flex: 1,
    color: lightColors.textPrimary,
  },
  loadingContainer: {
    flex: 1,
    minHeight: 360,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    ...typography.body,
    marginTop: spacing.sm,
    color: lightColors.textSecondary,
  },
  stateContainer: {
    flex: 1,
    minHeight: 360,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
  },
  stateIcon: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.neutralBackground,
  },
  stateTitle: {
    ...typography.sectionTitle,
    marginTop: spacing.md,
    textAlign: 'center',
    color: lightColors.textPrimary,
  },
  stateMessage: {
    ...typography.body,
    maxWidth: 300,
    marginTop: spacing.xs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  retryButton: {
    width: '100%',
    marginTop: spacing.lg,
  },
  readyContent: {
    flex: 1,
  },
  readOnlyNotice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginTop: spacing.lg,
    padding: spacing.sm,
    borderRadius: radii.input,
    backgroundColor: lightColors.neutralBackground,
  },
  readOnlyText: {
    ...typography.supporting,
    flex: 1,
    color: lightColors.neutral,
  },
  action: {
    marginTop: spacing.lg,
  },
});
