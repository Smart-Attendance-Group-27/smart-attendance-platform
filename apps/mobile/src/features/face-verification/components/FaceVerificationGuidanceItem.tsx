import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';

type FaceVerificationGuidanceItemProps = {
  icon: SymbolViewProps['name'];
  message: string;
  title: string;
};

export function FaceVerificationGuidanceItem({
  icon,
  message,
  title,
}: FaceVerificationGuidanceItemProps) {
  return (
    <View style={styles.row}>
      <View style={styles.iconContainer}>
        <SymbolView
          name={icon}
          size={24}
          tintColor={lightColors.primaryInteraction}
        />
      </View>
      <View style={styles.copy}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.message}>{message}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  iconContainer: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.input,
    backgroundColor: lightColors.primaryLight,
  },
  copy: {
    flex: 1,
  },
  title: {
    ...typography.cardTitle,
    color: lightColors.textPrimary,
  },
  message: {
    ...typography.supporting,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
});
