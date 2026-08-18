import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
} from 'react-native';
import { SymbolView } from 'expo-symbols';

import { AppInput } from '../../../components/ui/AppInput';
import { ScreenContainer } from '../../../components/ui/ScreenContainer';
import { lightColors, spacing, typography, radii } from '../../../theme';
import type { Course } from '../mockCoursesData';

type CourseListScreenProps = {
  courses: Course[];
  onSelectCourse: (courseId: string) => void;
  onBackPress?: () => void;
};

export function CourseListScreen({
  courses,
  onSelectCourse,
  onBackPress,
}: CourseListScreenProps) {
  const [searchQuery, setSearchQuery] = useState('');

  // Filter courses based on code or title match
  const filteredCourses = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return courses;
    return courses.filter(
      (c) =>
        c.code.toLowerCase().includes(query) ||
        c.title.toLowerCase().includes(query)
    );
  }, [courses, searchQuery]);

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  return (
    <ScreenContainer scrollable={false}>
      {/* Page Header */}
      <View style={styles.header}>
        <Pressable
          onPress={onBackPress}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <SymbolView
            name={{
              ios: 'chevron.left',
              android: 'arrow_back',
              web: 'arrow_back',
            }}
            size={24}
            tintColor={lightColors.textPrimary}
          />
        </Pressable>
        <Text style={styles.headerTitle}>Courses</Text>
      </View>

      <View style={styles.content}>
        {/* Search Input */}
        <AppInput
          placeholder="Search by course name or code"
          value={searchQuery}
          onChangeText={setSearchQuery}
          containerStyle={styles.searchContainer}
          inputContainerStyle={styles.searchInputContainer}
          rightElement={
            searchQuery.length > 0 ? (
              <Pressable onPress={handleClearSearch} style={styles.clearBtn}>
                <SymbolView
                  name={{
                    ios: 'xmark.circle.fill',
                    android: 'cancel',
                    web: 'cancel',
                  }}
                  size={20}
                  tintColor={lightColors.textSecondary}
                />
              </Pressable>
            ) : (
              <SymbolView
                name={{
                  ios: 'magnifyingglass',
                  android: 'search',
                  web: 'search',
                }}
                size={20}
                tintColor={lightColors.textSecondary}
              />
            )
          }
        />

        {/* Filter chips (only visible when not searching, or always Sem 1) */}
        {searchQuery.length === 0 ? (
          <View style={styles.chipsRow}>
            <View style={styles.chip}>
              <SymbolView
                name={{
                  ios: 'slider.horizontal.3',
                  android: 'filter_list',
                  web: 'filter_list',
                }}
                size={14}
                tintColor={lightColors.primary}
                style={styles.chipIcon}
              />
              <Text style={styles.chipText}>Semester 1, 2026</Text>
            </View>
          </View>
        ) : (
          <Text style={styles.searchResultCount}>
            {filteredCourses.length} {filteredCourses.length === 1 ? 'result' : 'results'} for “{searchQuery}”
          </Text>
        )}

        {/* Course Cards or Empty State */}
        {filteredCourses.length > 0 ? (
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.scrollList}
          >
            {filteredCourses.map((course) => (
              <Pressable
                key={course.id}
                onPress={() => onSelectCourse(course.id)}
                style={({ pressed }) => [
                  styles.card,
                  pressed && styles.cardPressed,
                ]}
              >
                <View style={styles.cardHeader}>
                  <View style={styles.cardHeaderLeft}>
                    <Text style={styles.cardTitle}>
                      {course.code} — {course.title}
                    </Text>
                    <Text style={styles.cardSubtitle}>
                      {course.lecturer} · {course.semester}
                    </Text>
                  </View>
                  <SymbolView
                    name={{
                      ios: 'chevron.right',
                      android: 'chevron_right',
                      web: 'chevron_right',
                    }}
                    size={20}
                    tintColor={lightColors.textSecondary}
                  />
                </View>

                <View style={styles.divider} />

                <View style={styles.cardFooter}>
                  <Text style={styles.attendanceSummary}>
                    {course.attendedSessions} of {course.totalSessions} sessions attended
                  </Text>
                  <Text style={styles.attendancePercentage}>
                    {course.attendancePercentage}%
                  </Text>
                </View>
              </Pressable>
            ))}
          </ScrollView>
        ) : (
          <View style={styles.emptyStateContainer}>
            <View style={styles.emptyIconContainer}>
              <SymbolView
                name={{
                  ios: 'magnifyingglass',
                  android: 'search',
                  web: 'search',
                }}
                size={30}
                tintColor={lightColors.neutral}
              />
            </View>
            <Text style={styles.emptyTitle}>No results found</Text>
            <Text style={styles.emptyDescription}>
              Try a different course name or code.
            </Text>
          </View>
        )}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
    marginTop: spacing.sm,
  },
  backBtn: {
    padding: spacing.xs,
    marginRight: spacing.xs,
    marginLeft: -spacing.xs,
    borderRadius: radii.full,
  },
  headerTitle: {
    ...typography.screenTitle,
    color: lightColors.textPrimary,
  },
  content: {
    flex: 1,
  },
  searchContainer: {
    marginBottom: spacing.xs,
  },
  searchInputContainer: {
    borderRadius: radii.input,
    height: 48,
  },
  clearBtn: {
    padding: 4,
  },
  chipsRow: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: lightColors.primaryLight,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: radii.full,
    borderWidth: 1,
    borderColor: '#C3D2F5',
  },
  chipIcon: {
    marginRight: 6,
  },
  chipText: {
    ...typography.caption,
    fontWeight: '600',
    color: lightColors.primary,
  },
  searchResultCount: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginBottom: spacing.md,
  },
  scrollList: {
    paddingBottom: spacing.xl,
    gap: spacing.md,
  },
  card: {
    backgroundColor: lightColors.surface,
    borderRadius: radii.card,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  cardPressed: {
    opacity: 0.9,
    backgroundColor: '#F3F4F6',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  cardHeaderLeft: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  cardTitle: {
    ...typography.cardTitle,
    color: lightColors.textPrimary,
  },
  cardSubtitle: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 4,
  },
  divider: {
    height: 1,
    backgroundColor: lightColors.border,
    marginVertical: spacing.sm,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  attendanceSummary: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
  attendancePercentage: {
    ...typography.cardTitle,
    fontWeight: '800',
    color: lightColors.primaryInteraction,
  },
  emptyStateContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 60,
  },
  emptyIconContainer: {
    width: 64,
    height: 64,
    borderRadius: radii.full,
    backgroundColor: lightColors.neutralBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  emptyTitle: {
    ...typography.cardTitle,
    fontWeight: '700',
    color: lightColors.textPrimary,
  },
  emptyDescription: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 6,
  },
});
