import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { AppButton } from '../ui';
import { lightColors, radii, spacing, typography } from '../../theme';

export function ActiveSessionCard() {
  return (
    <View style={styles.card}>
      <View style={styles.headingRow}>
        <View style={styles.headingCopy}>
          <Text style={styles.course}>
            CS3203 · Software Engineering Project
          </Text>
          <Text style={styles.title}>Architecture Review Lecture</Text>
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
        <View style={styles.detail}>
          <SymbolView
            name={{ ios: 'clock', android: 'schedule', web: 'schedule' }}
            size={17}
            tintColor={lightColors.textSecondary}
          />
          <Text style={styles.detailText}>10:00–12:00</Text>
        </View>
        <View style={styles.detail}>
          <SymbolView
            name={{ ios: 'location', android: 'location_on', web: 'location_on' }}
            size={17}
            tintColor={lightColors.textSecondary}
          />
          <Text style={styles.detailText}>Lecture Hall 02</Text>
        </View>
      </View>

      <View style={styles.button}>
        <AppButton title="Start attendance" />
      </View>
      <Text style={styles.closingText}>Check-in closes in 18 min</Text>
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
