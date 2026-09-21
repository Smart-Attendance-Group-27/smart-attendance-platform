import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AppButton } from '../../../components/ui';
import { lightColors, spacing, typography } from '../../../theme';
import type { AttendanceService } from '../services/attendanceService';
import type { MyAttendance } from '../types/myAttendance';

type Props = {
  sessionId: string;
  attendanceService: AttendanceService;
  onReturnHome: () => void;
  onStartCheckIn: () => void;
  onOpenQrScanner?: () => void;
};

function canRecover(state: MyAttendance): boolean {
  return state.sessionState === 'active' &&
    state.verification.attemptStatus === 'in_progress' &&
    state.initialCheckIn === null &&
    state.verification.geofenceStatus === 'passed' &&
    (!state.requiresFaceVerification || state.verification.faceStatus === 'passed');
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString();
}

export function AttendanceProgressScreen({
  sessionId, attendanceService, onReturnHome, onStartCheckIn, onOpenQrScanner,
}: Props) {
  const [attendance, setAttendance] = useState<MyAttendance | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recoveryAttempted = useRef<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async (pull = false) => {
    const request = ++requestId.current;
    if (pull) setRefreshing(true);
    try {
      let result = await attendanceService.getMyAttendance(sessionId);
      if (result.status === 'loaded' && canRecover(result.attendance) &&
          recoveryAttempted.current !== sessionId) {
        recoveryAttempted.current = sessionId;
        await attendanceService.checkIn(sessionId);
        result = await attendanceService.getMyAttendance(sessionId);
      }
      if (request !== requestId.current) return;
      if (result.status === 'loaded') {
        setAttendance(result.attendance);
        setError(null);
      } else {
        setError(result.status === 'not-found'
          ? 'This attendance session is unavailable.'
          : 'Could not load attendance. Check your connection and try again.');
      }
    } catch {
      if (request === requestId.current) setError('Could not load attendance. Try again.');
    } finally {
      if (request === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [attendanceService, sessionId]);

  useFocusEffect(useCallback(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load]));

  useEffect(() => {
    if (attendance?.sessionState !== 'active') return;
    const timer = setInterval(() => { void load(); }, 15_000);
    return () => clearInterval(timer);
  }, [attendance?.sessionState, load]);

  return (
    <View style={styles.root}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />}
      >
        <Text accessibilityRole="header" style={styles.title}>Attendance progress</Text>
        {loading ? <ActivityIndicator accessibilityLabel="Loading attendance progress" /> : null}
        {error ? (
          <View style={styles.card}>
            <Text>{error}</Text>
            <AppButton title="Retry" onPress={() => void load()} />
          </View>
        ) : null}
        {attendance ? (
          <>
            <Text style={styles.course}>{attendance.courseCode} · {attendance.courseName}</Text>
            <Text style={styles.session}>{attendance.sessionTitle}</Text>
            <View style={styles.card}>
              <Text style={styles.heading}>Initial check-in</Text>
              {attendance.initialCheckIn ? (
                <>
                  <Text accessibilityRole="text" style={styles.outcome}>
                    Initial check-in complete ({attendance.initialCheckIn.status === 'late_checked_in'
                      ? 'late' : 'on time'})
                  </Text>
                  <Text>Checked in at {formatTime(attendance.initialCheckIn.checkedInAt)}</Text>
                </>
              ) : (
                <Text>{attendance.verification.attemptStatus === 'failed'
                  ? `Verification failed${attendance.verification.failureReason
                    ? `: ${attendance.verification.failureReason}` : ''}`
                  : attendance.verification.attemptStatus === 'in_progress'
                    ? 'Verification in progress' : 'Check-in has not started'}</Text>
              )}
            </View>
            <View style={styles.card}>
              <Text style={styles.heading}>Final attendance</Text>
              {attendance.finalAttendance ? (
                <>
                  <Text style={styles.outcome}>
                    Final: {attendance.finalAttendance.status[0].toUpperCase() +
                      attendance.finalAttendance.status.slice(1)}
                  </Text>
                  <Text>{attendance.finalAttendance.source === 'manual'
                    ? 'Set by your lecturer' : 'Recorded when the session closed'}</Text>
                </>
              ) : (
                <Text>{attendance.sessionState === 'cancelled'
                  ? 'Session cancelled' : 'Awaiting final attendance'}</Text>
              )}
            </View>
            {attendance.canStartCheckIn && !attendance.initialCheckIn ? (
              <AppButton title="Start check-in" onPress={onStartCheckIn} />
            ) : null}
            {attendance.qrEnabled && attendance.initialCheckIn &&
              attendance.sessionState === 'active' && onOpenQrScanner ? (
                <AppButton title="Scan QR" onPress={onOpenQrScanner} variant="secondary" />
              ) : null}
            <AppButton title="Return home" onPress={onReturnHome} variant="secondary" />
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: lightColors.background },
  content: { padding: spacing.lg, gap: spacing.md },
  title: { ...typography.screenTitle, color: lightColors.textPrimary },
  course: { ...typography.supporting, color: lightColors.primaryInteraction, fontWeight: '700' },
  session: { ...typography.sectionTitle, color: lightColors.textPrimary },
  card: { padding: spacing.md, gap: spacing.xs, backgroundColor: lightColors.surface,
    borderRadius: 12, borderWidth: 1, borderColor: lightColors.border },
  heading: { ...typography.sectionTitle, color: lightColors.textPrimary },
  outcome: { ...typography.body, color: lightColors.textPrimary, fontWeight: '700' },
});
