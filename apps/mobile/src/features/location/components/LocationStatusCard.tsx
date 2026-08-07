import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';

export type LocationStatusTone =
  | 'info'
  | 'success'
  | 'warning'
  | 'error';

type LocationStatusCardProps = {
  action?: ReactNode;
  icon: SymbolViewProps['name'];
  loading?: boolean;
  message: string;
  title: string;
  tone: LocationStatusTone;
};

const toneColors = {
  info: {
    foreground: lightColors.info,
    background: lightColors.infoBackground,
  },
  success: {
    foreground: lightColors.success,
    background: lightColors.successBackground,
  },
  warning: {
    foreground: lightColors.warning,
    background: lightColors.warningBackground,
  },
  error: {
    foreground: lightColors.error,
    background: lightColors.errorBackground,
  },
} as const;

export function LocationStatusCard({
  action,
  icon,
  loading = false,
  message,
  title,
  tone,
}: LocationStatusCardProps) {
  const colors = toneColors[tone];

  return (
    <View
      style={[
        styles.card,
        {
          borderColor: colors.foreground,
          backgroundColor: colors.background,
        },
      ]}
    >
      <View
        accessible={!loading}
        accessibilityLabel={`Location status: ${title}. ${message}`}
        accessibilityLiveRegion={tone === 'error' ? 'assertive' : 'polite'}
        accessibilityRole={tone === 'error' ? 'alert' : undefined}
        style={styles.statusContent}
      >
        <View
          style={[
            styles.iconContainer,
            { backgroundColor: lightColors.surface },
          ]}
        >
          {loading ? (
            <ActivityIndicator
              accessible
              accessibilityLabel="Checking classroom location"
              accessibilityRole="progressbar"
              accessibilityState={{ busy: true }}
              color={colors.foreground}
              size="small"
            />
          ) : (
            <SymbolView
              name={icon}
              size={26}
              tintColor={colors.foreground}
            />
          )}
        </View>

        <View style={styles.copy}>
          <Text style={[styles.title, { color: colors.foreground }]}>
            {title}
          </Text>
          <Text style={styles.message}>{message}</Text>
        </View>
      </View>

      {action ? <View style={styles.action}>{action}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: spacing.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderRadius: radii.card,
  },
  statusContent: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  iconContainer: {
    width: 48,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.input,
  },
  copy: {
    flex: 1,
  },
  title: {
    ...typography.cardTitle,
  },
  message: {
    ...typography.supporting,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
  action: {
    marginTop: spacing.md,
  },
});
