import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { AppButton } from '../ui';
import { lightColors, radii, spacing, typography } from '../../theme';
import type { AttendanceSession } from '../../features/dashboard/types';

type ActiveSessionCardProps = {
  session?: AttendanceSession | null | (Partial<Record<string, any>> & AttendanceSession);
  onStart?: () => void;
};

function formatTimeRange(start?: string, end?: string) {
  if (!start || !end) return undefined;
  try {
    const s = new Date(start);
    const e = new Date(end);
    const opts: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' };
    return `${s.toLocaleTimeString([], opts)}–${e.toLocaleTimeString([], opts)}`;
  } catch {
    return undefined;
  }
}

function computeClosingText(end?: string) {
  if (!end) return 'Check-in closes soon';
  const minutes = Math.max(0, Math.floor((new Date(end).getTime() - Date.now()) / 60000));
  if (minutes <= 0) return 'Check-in closed';
  return `Check-in closes in ${minutes} min`;
}

export function ActiveSessionCard({ session, onStart }: ActiveSessionCardProps) {
  const courseLabel = session ? `${session.courseCode} · ${session.courseName}` : '—';
  const title = (session as any)?.sessionTitle ?? session?.courseName ?? '';
  const timeRange = formatTimeRange((session as any)?.startTime ?? (session && (session as any).startTime), (session as any)?.endTime ?? (session && (session as any).endTime));
  const venue = (session as any)?.venue ?? '';
  const closingText = computeClosingText((session as any)?.endTime ?? (session && (session as any).endTime));

  return (
    <View style={styles.card}>
      <View style={styles.headingRow}>
        <View style={styles.headingCopy}>
          <Text style={styles.course}>{courseLabel}</Text>
          <Text style={styles.title}>{title}</Text>
        </View>
        <View style={styles.activeChip}>
          <SymbolView
            name={{ ios: 'clock', android: 'schedule', web: 'schedule' }}
            size={14}
            tintColor={lightColors.primaryInteraction}
          />
          <Text style={styles.activeChipText}>Active now</Text>
        </View>
      </View>

      <View style={styles.details}>
        {timeRange ? (
          <View style={styles.detail}>
            <SymbolView
              name={{ ios: 'clock', android: 'schedule', web: 'schedule' }}
              size={17}
              tintColor={lightColors.textSecondary}
            />
            <Text style={styles.detailText}>{timeRange}</Text>
          </View>
        ) : null}

        {venue ? (
          <View style={styles.detail}>
            <SymbolView
              name={{ ios: 'location', android: 'location_on', web: 'location_on' }}
              size={17}
              tintColor={lightColors.textSecondary}
            />
            <Text style={styles.detailText}>{venue}</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.button}>
        <AppButton title="Start attendance" onPress={onStart} />
      </View>
      <Text style={styles.closingText}>{closingText}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginBottom: spacing.xl,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: '#C3D2F5',
    borderRadius: radii.card,
    backgroundColor: lightColors.primaryLight,
    shadowColor: lightColors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 3,
  },
  headingRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.xs,
  },
  headingCopy: {
    flex: 1,
  },
  course: {
    ...typography.supporting,
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  title: {
    ...typography.cardTitle,
    marginTop: spacing.xxs,
    color: lightColors.textPrimary,
  },
  activeChip: {
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.full,
    backgroundColor: lightColors.infoBackground,
  },
  activeChipText: {
    ...typography.caption,
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  details: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  detail: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xxs,
  },
  detailText: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
  button: {
    marginTop: 14,
  },
  closingText: {
    ...typography.supporting,
    marginTop: 10,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
});
