import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { ActivityIndicator, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, radii, spacing, typography } from '../../../theme';
import { AttendanceTimeline } from '../components/AttendanceTimeline';
import {
  formatAttendanceDate,
  formatAttendanceDateTime,
  formatAttendanceTimeRange,
} from '../utils/formatAttendanceSession';
import {
  buildAttendanceSteps,
  nextCheckInAction,
  stepProgress,
  summarizeAttendance,
  type SummaryTone,
} from '../utils/attendanceSteps';
import type { AttendanceService } from '../services/attendanceService';
import type { MyAttendance } from '../types/myAttendance';
import type { QrBatchProgress, QrProgress } from '../../qr/types/qrProgress';
import type { QrProgressService } from '../../qr/services/qrProgressService';

type Props = {
  sessionId: string;
  attendanceService: AttendanceService;
  qrProgressService?: QrProgressService;
  onReturnHome: () => void;
  onStartCheckIn: () => void;
  onContinueToFaceVerification?: (locationWaived: boolean) => void;
  onOpenQrScanner?: (qrSessionId: string) => void;
};

const REFRESH_INTERVAL_MS = 15_000;

// Every required step already passed (or was waived) but the check-in was
// not written, e.g. the app closed mid-request. Asking the server again lets
// it finish the check-in from the evidence it already has.
function canRecover(state: MyAttendance): boolean {
  const locationDone = state.verificationPolicy.geofence !== 'required' ||
    state.verification.geofenceStatus === 'passed';
  const faceDone = state.verificationPolicy.face === 'not_required' ||
    state.verification.faceStatus === 'passed';
  return state.sessionState === 'active' &&
    state.verification.attemptStatus === 'in_progress' &&
    state.initialCheckIn === null &&
    locationDone && faceDone;
}

const TONE_COLORS: Record<SummaryTone, { color: string; background: string; icon: SymbolViewProps['name'] }> = {
  success: {
    color: lightColors.success, background: lightColors.successBackground,
    icon: { ios: 'checkmark.circle.fill', android: 'check_circle', web: 'check_circle' },
  },
  warning: {
    color: lightColors.warning, background: lightColors.warningBackground,
    icon: { ios: 'exclamationmark.triangle.fill', android: 'warning', web: 'warning' },
  },
  error: {
    color: lightColors.error, background: lightColors.errorBackground,
    icon: { ios: 'xmark.circle.fill', android: 'cancel', web: 'cancel' },
  },
  info: {
    color: lightColors.info, background: lightColors.infoBackground,
    icon: { ios: 'clock.fill', android: 'schedule', web: 'schedule' },
  },
  neutral: {
    color: lightColors.neutral, background: lightColors.neutralBackground,
    icon: { ios: 'info.circle.fill', android: 'info', web: 'info' },
  },
};

function batchLabel(batch: QrBatchProgress, sessionOpen: boolean): string {
  if (batch.voided) return 'Voided';
  if (!batch.required) return 'Not required';
  if (batch.passed) return 'Completed';
  return sessionOpen ? 'Pending' : 'Missed';
}

function SessionHeader({ attendance }: { attendance: MyAttendance }) {
  const meta = [
    attendance.venue,
    `${formatAttendanceDate(attendance.scheduledStartAt)} · ${formatAttendanceTimeRange(
      attendance.scheduledStartAt, attendance.scheduledEndAt,
    )}`,
  ].filter(Boolean).join(' · ');
  return (
    <View style={styles.card}>
      <View style={styles.courseChip}>
        <Text style={styles.courseChipText}>{attendance.courseCode}</Text>
      </View>
      <Text accessibilityRole="header" style={styles.sessionTitle}>{attendance.sessionTitle}</Text>
      <Text style={styles.courseName}>{attendance.courseName}</Text>
      <Text style={styles.meta}>{meta}</Text>
    </View>
  );
}

function SummaryCard({ attendance, completed, total }: {
  attendance: MyAttendance; completed: number; total: number;
}) {
  const summary = summarizeAttendance(attendance);
  const tone = TONE_COLORS[summary.tone];
  const showProgress = !attendance.finalAttendance && attendance.sessionState !== 'cancelled' && total > 0;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <View
      accessible
      accessibilityLabel={`${summary.title}. ${summary.message}`}
      style={[styles.card, styles.summaryCard, { borderLeftColor: tone.color }]}
    >
      <View style={styles.summaryRow}>
        <View style={[styles.summaryIcon, { backgroundColor: tone.background }]}>
          <SymbolView name={tone.icon} size={22} tintColor={tone.color} />
        </View>
        <View style={styles.summaryText}>
          <Text style={styles.summaryTitle}>{summary.title}</Text>
          <Text style={styles.summaryMessage}>{summary.message}</Text>
        </View>
      </View>
      {attendance.initialCheckIn ? (
        <Text style={styles.meta}>
          Checked in at {formatAttendanceDateTime(attendance.initialCheckIn.checkedInAt)}
        </Text>
      ) : null}
      {showProgress ? (
        <View style={styles.progressBlock}>
          <View
            accessibilityRole="progressbar"
            accessibilityValue={{ min: 0, max: total, now: completed }}
            style={styles.progressTrack}
          >
            <View style={[styles.progressFill, { width: `${percent}%` }]} />
          </View>
          <Text style={styles.progressLabel}>{completed} of {total} steps completed</Text>
        </View>
      ) : null}
    </View>
  );
}

function QrChecks({ attendance, qrProgress, onOpenQrScanner }: {
  attendance: MyAttendance;
  qrProgress: QrProgress;
  onOpenQrScanner?: (qrSessionId: string) => void;
}) {
  const sessionOpen = attendance.sessionState === 'active';
  const active = qrProgress.activeBatch;
  const canScan = sessionOpen && attendance.initialCheckIn && active?.required && !active.passed;
  if (!qrProgress.batches.length && !canScan) return null;
  return (
    <View style={styles.card}>
      <Text style={styles.cardHeading}>QR checks</Text>
      {canScan && onOpenQrScanner ? (
        <View style={styles.qrCallout}>
          <Text style={styles.qrCalloutText}>A QR check is open now.</Text>
          <AppButton
            accessibilityLabel="Scan QR"
            onPress={() => onOpenQrScanner(active!.qrSessionId)}
            title="Scan QR"
          />
        </View>
      ) : null}
      {qrProgress.batches.map((batch, index) => (
        <View key={batch.qrSessionId} style={styles.batchRow}>
          <Text style={styles.batchName}>Check {qrProgress.batches.length - index}</Text>
          <Text style={[styles.batchStatus, batch.voided && styles.batchStatusMuted]}>
            {batchLabel(batch, sessionOpen)}
          </Text>
        </View>
      ))}
      {qrProgress.batches.some((batch) => batch.voided) ? (
        <Text style={styles.meta}>Voided checks were cancelled by your lecturer and do not count.</Text>
      ) : null}
    </View>
  );
}

export function AttendanceProgressScreen({
  sessionId, attendanceService, qrProgressService, onReturnHome, onStartCheckIn,
  onContinueToFaceVerification, onOpenQrScanner,
}: Props) {
  const [attendance, setAttendance] = useState<MyAttendance | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qrProgress, setQrProgress] = useState<QrProgress | null>(null);
  const [qrError, setQrError] = useState(false);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
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
        if (result.attendance.qrEnabled && qrProgressService) {
          try {
            const qrResult = await qrProgressService.getQrProgress(sessionId);
            if (request !== requestId.current) return;
            setQrProgress(qrResult.status === 'loaded' ? qrResult.progress : null);
            setQrError(qrResult.status !== 'loaded');
          } catch {
            if (request !== requestId.current) return;
            setQrProgress(null);
            setQrError(true);
          }
        } else {
          setQrProgress(null);
          setQrError(false);
        }
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
  }, [attendanceService, qrProgressService, sessionId]);

  useFocusEffect(useCallback(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load]));

  // Keeps the screen current while the session runs, so a waiver or a new
  // QR check shows up without the student doing anything.
  useEffect(() => {
    if (attendance?.sessionState !== 'active') return;
    const timer = setInterval(() => { void load(); }, REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [attendance?.sessionState, load]);

  const continueToFace = useCallback(async () => {
    if (!attendance || starting) return;
    setActionError(null);
    if (attendance.verificationPolicy.geofence !== 'waived') {
      onContinueToFaceVerification?.(false);
      return;
    }
    setStarting(true);
    try {
      const result = await attendanceService.startVerificationWithoutLocation(sessionId);
      if (result.status === 'started' && !result.initialCheckIn) {
        onContinueToFaceVerification?.(true);
      } else if (result.status === 'started' || result.status === 'already_checked_in') {
        await load();
      } else {
        setActionError('Could not continue check-in. Pull down to refresh and try again.');
      }
    } catch {
      setActionError('Could not continue check-in. Check your connection and try again.');
    } finally {
      setStarting(false);
    }
  }, [attendance, attendanceService, load, onContinueToFaceVerification, sessionId, starting]);

  const steps = attendance ? buildAttendanceSteps(attendance, qrProgress, qrError) : [];
  const { completed, total } = stepProgress(steps);
  const action = attendance ? nextCheckInAction(attendance) : 'none';

  return (
    <ScreenContainer
      scrollable
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />}
    >
      <Text accessibilityRole="header" style={styles.title}>Attendance progress</Text>

      {loading && !attendance ? (
        <View style={styles.stateBlock}>
          <ActivityIndicator
            accessibilityLabel="Loading attendance progress"
            color={lightColors.primaryInteraction}
            size="large"
          />
          <Text style={styles.stateText}>Loading attendance…</Text>
        </View>
      ) : null}

      {error ? (
        <View style={[styles.card, styles.errorCard]}>
          <SymbolView
            name={{ ios: 'exclamationmark.triangle.fill', android: 'warning', web: 'warning' }}
            size={24}
            tintColor={lightColors.error}
          />
          <Text style={styles.errorText}>{error}</Text>
          <AppButton title="Retry" variant="secondary" onPress={() => void load()} />
        </View>
      ) : null}

      {attendance ? (
        <>
          <SessionHeader attendance={attendance} />
          <SummaryCard attendance={attendance} completed={completed} total={total} />

          <View style={styles.card}>
            <Text style={styles.cardHeading}>Verification steps</Text>
            <AttendanceTimeline steps={steps} />
          </View>

          {qrProgress && attendance.qrEnabled ? (
            <QrChecks
              attendance={attendance}
              onOpenQrScanner={onOpenQrScanner}
              qrProgress={qrProgress}
            />
          ) : null}

          {actionError ? (
            <Text accessibilityRole="alert" style={styles.actionError}>{actionError}</Text>
          ) : null}

          <View style={styles.actions}>
            {action === 'start_check_in' ? (
              <AppButton title="Start check-in" onPress={onStartCheckIn} />
            ) : null}
            {action === 'continue_to_face' ? (
              <AppButton
                loading={starting}
                loadingTitle="Continuing…"
                onPress={() => void continueToFace()}
                title="Continue to face verification"
              />
            ) : null}
            <AppButton title="Return home" onPress={onReturnHome} variant="secondary" />
          </View>
        </>
      ) : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.md, paddingBottom: spacing.xxl },
  title: { ...typography.screenTitle, color: lightColors.textPrimary },
  card: {
    padding: spacing.md,
    gap: spacing.xs,
    backgroundColor: lightColors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: lightColors.border,
  },
  cardHeading: {
    ...typography.cardTitle,
    marginBottom: spacing.xs,
    color: lightColors.textPrimary,
  },
  courseChip: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.small,
    backgroundColor: lightColors.primaryLight,
  },
  courseChipText: {
    ...typography.caption,
    fontWeight: '700',
    color: lightColors.primary,
  },
  sessionTitle: { ...typography.sectionTitle, color: lightColors.textPrimary },
  courseName: { ...typography.body, color: lightColors.textSecondary },
  meta: { ...typography.supporting, color: lightColors.textSecondary },
  summaryCard: { borderLeftWidth: 4 },
  summaryRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  summaryIcon: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
  },
  summaryText: { flex: 1, minWidth: 0 },
  summaryTitle: { ...typography.sectionTitle, color: lightColors.textPrimary },
  summaryMessage: { ...typography.supporting, marginTop: 2, color: lightColors.textSecondary },
  progressBlock: { marginTop: spacing.xs, gap: spacing.xxs },
  progressTrack: {
    height: 6,
    overflow: 'hidden',
    borderRadius: radii.full,
    backgroundColor: lightColors.neutralBackground,
  },
  progressFill: {
    height: '100%',
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryInteraction,
  },
  progressLabel: { ...typography.caption, color: lightColors.textSecondary },
  qrCallout: {
    gap: spacing.xs,
    padding: spacing.sm,
    marginBottom: spacing.xs,
    borderRadius: radii.input,
    backgroundColor: lightColors.primaryLight,
  },
  qrCalloutText: { ...typography.supporting, fontWeight: '700', color: lightColors.primary },
  batchRow: {
    minHeight: 32,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: lightColors.border,
  },
  batchName: { ...typography.supporting, color: lightColors.textPrimary },
  batchStatus: { ...typography.supporting, fontWeight: '700', color: lightColors.textPrimary },
  batchStatusMuted: { color: lightColors.neutral },
  stateBlock: { minHeight: 240, alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
  stateText: { ...typography.body, color: lightColors.textSecondary },
  errorCard: { alignItems: 'center', gap: spacing.sm },
  errorText: { ...typography.body, textAlign: 'center', color: lightColors.textPrimary },
  actionError: { ...typography.supporting, color: lightColors.error },
  actions: { gap: spacing.sm },
});
