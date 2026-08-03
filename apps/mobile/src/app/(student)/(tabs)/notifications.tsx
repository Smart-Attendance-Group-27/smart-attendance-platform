import { StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import {
  lightColors,
  spacing,
  typography,
} from '../../../theme';

export default function NotificationsScreen() {
  return (
    <ScreenContainer>
      <View style={styles.content}>
        <Text style={styles.title}>Notifications</Text>

        <Text style={styles.description}>
          Attendance updates and important session alerts will appear here.
        </Text>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.xs,
  },

  title: {
    ...typography.screenTitle,
    color: lightColors.textPrimary,
  },

  description: {
    ...typography.body,
    color: lightColors.textSecondary,
  },
});