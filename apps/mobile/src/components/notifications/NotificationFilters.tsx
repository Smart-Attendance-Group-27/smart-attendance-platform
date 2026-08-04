import { Pressable, StyleSheet, Text, View } from 'react-native';

import { lightColors, radii, spacing, typography } from '../../theme';
import type { NotificationFilter } from './notification.types';

type NotificationFiltersProps = {
  selectedFilter: NotificationFilter;
  onSelectFilter: (filter: NotificationFilter) => void;
};

const filters: { label: string; value: NotificationFilter }[] = [
  { label: 'All', value: 'all' },
  { label: 'Attendance', value: 'attendance' },
  { label: 'System', value: 'system' },
];

export function NotificationFilters({
  selectedFilter,
  onSelectFilter,
}: NotificationFiltersProps) {
  return (
    <View accessibilityRole="tablist" style={styles.container}>
      {filters.map((filter) => {
        const isSelected = filter.value === selectedFilter;

        return (
          <Pressable
            accessibilityLabel={`Show ${filter.label.toLowerCase()} notifications`}
            accessibilityRole="tab"
            accessibilityState={{ selected: isSelected }}
            hitSlop={2}
            key={filter.value}
            onPress={() => onSelectFilter(filter.value)}
            style={({ pressed }) => [
              styles.filter,
              isSelected ? styles.selectedFilter : styles.unselectedFilter,
              pressed && styles.pressed,
            ]}
          >
            <Text
              style={[
                styles.label,
                isSelected ? styles.selectedLabel : styles.unselectedLabel,
              ]}
            >
              {filter.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  filter: {
    minHeight: 40,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderRadius: radii.full,
  },
  selectedFilter: {
    borderColor: lightColors.primaryInteraction,
    backgroundColor: lightColors.primaryInteraction,
  },
  unselectedFilter: {
    borderColor: lightColors.border,
    backgroundColor: lightColors.surface,
  },
  pressed: {
    opacity: 0.75,
  },
  label: {
    ...typography.caption,
    fontSize: 13,
    fontWeight: '600',
  },
  selectedLabel: {
    color: lightColors.surface,
  },
  unselectedLabel: {
    color: lightColors.primaryInteraction,
  },
});
