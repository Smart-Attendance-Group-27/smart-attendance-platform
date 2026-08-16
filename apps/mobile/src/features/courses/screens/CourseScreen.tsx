import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';

import { ScreenContainer } from '../../../components/ui';
import { CourseSummaryCard, courseSummaries } from '../../../components/dashboard';
import { typography, spacing, lightColors } from '../../../theme';

export function CourseScreen() {
  return (
    <ScreenContainer scrollable contentContainerStyle={styles.container}>
      <Text accessibilityRole="header" style={styles.title}>My courses</Text>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.rail}
      >
        {courseSummaries.map((c) => (
          <CourseSummaryCard course={c} key={c.code} />
        ))}
      </ScrollView>

      <View style={styles.listHeading}>
        <Text style={styles.section}>All courses</Text>
      </View>

      <View style={styles.list}>
        {courseSummaries.map((c) => (
          <View key={c.code} style={styles.listItem}>
            <Text style={styles.courseLabel}>{c.code} — {c.title}</Text>
          </View>
        ))}
      </View>
    </ScreenContainer>
  );
}

export default CourseScreen;

const styles = StyleSheet.create({
  container: {
    paddingTop: spacing.xl,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
  },
  title: {
    ...typography.screenTitle,
    marginBottom: spacing.md,
    color: lightColors.textPrimary,
  },
  rail: {
    gap: spacing.md,
    paddingRight: spacing.lg,
    marginBottom: spacing.lg,
  },
  listHeading: {
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  section: {
    ...typography.sectionTitle,
    color: lightColors.textPrimary,
  },
  list: {
    gap: spacing.sm,
  },
  listItem: {
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  courseLabel: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
});
