import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { lightColors, radii, spacing, typography } from '../../../theme';
import type { NotificationPreferencesService } from '../services/notificationPreferencesService';
import type { NotificationPreference } from '../types/notificationPreference';

type Props = {
  onBack: () => void;
  service: NotificationPreferencesService;
};

export function NotificationPreferencesScreen({ onBack, service }: Props) {
  const [preferences, setPreferences] = useState<NotificationPreference[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'saving' | 'error'>('loading');

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      setPreferences(await service.getPreferences());
      setStatus('ready');
    } catch {
      setStatus('error');
    }
  }, [service]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = (typeCode: string, field: 'inAppEnabled' | 'pushEnabled') => {
    setPreferences((current) => current.map((preference) =>
      preference.typeCode === typeCode
        ? { ...preference, [field]: !preference[field] }
        : preference));
  };

  const save = async () => {
    setStatus('saving');
    try {
      setPreferences(await service.updatePreferences(preferences));
      setStatus('ready');
    } catch {
      setStatus('error');
    }
  };

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screen}>
      <View style={styles.header}>
        <Pressable accessibilityLabel="Back" accessibilityRole="button" onPress={onBack}>
          <Text style={styles.back}>Back</Text>
        </Pressable>
        <Text accessibilityRole="header" style={styles.title}>Notification preferences</Text>
      </View>

      {status === 'loading' ? (
        <ActivityIndicator accessibilityLabel="Loading notification preferences" size="large" />
      ) : null}
      {status === 'error' ? (
        <View style={styles.state}>
          <Text style={styles.error}>Preferences could not be loaded or saved.</Text>
          <AppButton accessibilityLabel="Retry notification preferences" onPress={() => void load()} title="Retry" />
        </View>
      ) : null}
      {status === 'ready' || status === 'saving' ? (
        <View style={styles.content}>
          {preferences.map((preference) => (
            <View key={preference.typeCode} style={styles.preference}>
              <Text style={styles.preferenceTitle}>{preference.description}</Text>
              <ToggleRow
                label="In-app"
                onValueChange={() => toggle(preference.typeCode, 'inAppEnabled')}
                value={preference.inAppEnabled}
              />
              <ToggleRow
                label="Push"
                onValueChange={() => toggle(preference.typeCode, 'pushEnabled')}
                value={preference.pushEnabled}
              />
            </View>
          ))}
          <AppButton
            accessibilityLabel="Save notification preferences"
            disabled={status === 'saving'}
            onPress={() => void save()}
            title={status === 'saving' ? 'Saving...' : 'Save'}
          />
        </View>
      ) : null}
    </ScreenContainer>
  );
}

function ToggleRow({ label, onValueChange, value }: { label: string; onValueChange: () => void; value: boolean }) {
  return (
    <View style={styles.toggleRow}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Switch accessibilityLabel={`${label} notifications`} onValueChange={onValueChange} value={value} />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, paddingBottom: spacing.xxl },
  header: { gap: spacing.sm, marginBottom: spacing.lg },
  back: { ...typography.button, color: lightColors.primaryInteraction },
  title: { ...typography.screenTitle, color: lightColors.textPrimary },
  content: { gap: spacing.md },
  preference: { gap: spacing.xs, padding: spacing.md, borderWidth: 1, borderColor: lightColors.border, borderRadius: radii.small, backgroundColor: lightColors.surface },
  preferenceTitle: { ...typography.sectionTitle, color: lightColors.textPrimary },
  toggleRow: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  toggleLabel: { ...typography.body, color: lightColors.textSecondary },
  state: { gap: spacing.md },
  error: { ...typography.body, color: lightColors.error },
});
