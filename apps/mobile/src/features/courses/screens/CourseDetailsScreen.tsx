import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
} from 'react-native';
import { SymbolView } from 'expo-symbols';

import { AppButton } from '../../../components/ui/AppButton';
import { ScreenContainer } from '../../../components/ui/ScreenContainer';
import { lightColors, spacing, typography, radii } from '../../../theme';
import type { Course, Session } from '../mockCoursesData';

type CourseDetailsScreenProps = {
  courses: Course[];
  courseId: string;
  onBack: () => void;
};

export function CourseDetailsScreen({
  courses,
  courseId,
  onBack,
}: CourseDetailsScreenProps) {
  const [activeTab, setActiveTab] = useState<'sessions' | 'attendance'>('sessions');
  // State to simulate identity verification flow (State 1: Active Now vs State 2: Waiting for QR check)
  const [isIdentityVerified, setIsIdentityVerified] = useState(false);

  const course = courses.find((c) => c.id === courseId);

  if (!course) {
    return (
      <ScreenContainer>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Course not found.</Text>
          <AppButton title="Go Back" onPress={onBack} style={{ marginTop: spacing.md }} />
        </View>
      </ScreenContainer>
    );
  }

  // Helper to render badge styles & icons
  const renderBadge = (status: Session['status']) => {
    switch (status) {
      case 'active':
        if (isIdentityVerified) {
          return (
            <View style={[styles.badge, styles.badgeWaiting]}>
              <SymbolView
                name={{
                  ios: 'face.smiling',
                  android: 'face',
                  web: 'face',
                }}
                size={14}
                tintColor="#1D4ED8"
                style={styles.badgeIcon}
              />
              <Text style={[styles.badgeText, styles.badgeTextWaiting]}>Waiting for QR check</Text>
            </View>
          );
        }
        return (
          <View style={[styles.badge, styles.badgeActive]}>
            <SymbolView
              name={{
                ios: 'clock',
                android: 'schedule',
                web: 'schedule',
              }}
              size={14}
              tintColor={lightColors.success}
              style={styles.badgeIcon}
            />
            <Text style={[styles.badgeText, styles.badgeTextActive]}>Active now</Text>
          </View>
        );
      case 'upcoming':
        return (
          <View style={[styles.badge, styles.badgeUpcoming]}>
            <SymbolView
              name={{
                ios: 'calendar',
                android: 'calendar_today',
                web: 'calendar_today',
              }}
              size={14}
              tintColor={lightColors.primary}
              style={styles.badgeIcon}
            />
            <Text style={[styles.badgeText, styles.badgeTextUpcoming]}>Upcoming</Text>
          </View>
        );
      case 'marked':
        return (
          <View style={[styles.badge, styles.badgeMarked]}>
            <SymbolView
              name={{
                ios: 'checkmark.circle',
                android: 'check_circle',
                web: 'check_circle',
              }}
              size={14}
              tintColor={lightColors.success}
              style={styles.badgeIcon}
            />
            <Text style={[styles.badgeText, styles.badgeTextMarked]}>Attendance marked</Text>
          </View>
        );
      case 'missed':
        return (
          <View style={[styles.badge, styles.badgeMissed]}>
            <SymbolView
              name={{
                ios: 'exclamationmark.triangle',
                android: 'warning',
                web: 'warning',
              }}
              size={14}
              tintColor={lightColors.error}
              style={styles.badgeIcon}
            />
            <Text style={[styles.badgeText, styles.badgeTextMissed]}>Missed</Text>
          </View>
        );
      case 'closed':
        return (
          <View style={[styles.badge, styles.badgeClosed]}>
            <SymbolView
              name={{
                ios: 'lock',
                android: 'lock_outline',
                web: 'lock_outline',
              }}
              size={14}
              tintColor={lightColors.neutral}
              style={styles.badgeIcon}
            />
            <Text style={[styles.badgeText, styles.badgeTextClosed]}>Session closed</Text>
          </View>
        );
      default:
        return null;
    }
  };

  // Group sessions by weekHeader
  const groupedSessions = course.sessions.reduce((acc, session) => {
    const key = session.weekHeader || 'Other';
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(session);
    return acc;
  }, {} as Record<string, Session[]>);

  return (
    <ScreenContainer scrollable={false}>
      {/* Detail Header */}
      <View style={styles.header}>
        <Pressable onPress={onBack} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Back to courses">
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
        <Text style={styles.headerTitle}>{course.code}</Text>
      </View>

      <Text style={styles.subheaderText}>
        {course.title} · {course.lecturer}
      </Text>

      {/* Segmented Control */}
      <View style={styles.segmentedContainer}>
        <Pressable
          onPress={() => setActiveTab('sessions')}
          style={[styles.segItem, activeTab === 'sessions' && styles.segItemActive]}
        >
          <Text style={[styles.segItemText, activeTab === 'sessions' && styles.segItemTextActive]}>
            Sessions
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setActiveTab('attendance')}
          style={[styles.segItem, activeTab === 'attendance' && styles.segItemActive]}
        >
          <Text style={[styles.segItemText, activeTab === 'attendance' && styles.segItemTextActive]}>
            Attendance
          </Text>
        </Pressable>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {activeTab === 'sessions' ? (
          <View>
            {/* Dashed summary attendance card */}
            <View style={styles.dashedCard}>
              <View style={styles.dashedCardRow}>
                <Text style={styles.dashedCardLabel}>Current attendance</Text>
                <Text style={styles.dashedCardValue}>{course.attendancePercentage}%</Text>
              </View>
              <Text style={styles.dashedCardSubtext}>
                {course.attendedSessions} of {course.totalSessions} completed sessions attended
              </Text>
            </View>

            {/* Simulated state toggle helper */}
            <Pressable
              onPress={() => setIsIdentityVerified(!isIdentityVerified)}
              style={styles.simulationHelper}
            >
              <Text style={styles.simulationHelperText}>
                {isIdentityVerified
                  ? '🔄 Toggle to "Active now" (Start Attendance)'
                  : '🔄 Toggle to "Waiting for QR Check"'}
              </Text>
            </Pressable>

            {/* Sessions grouped by week */}
            {Object.entries(groupedSessions).map(([week, sessions]) => (
              <View key={week} style={styles.weekGroup}>
                <Text style={styles.weekHead}>{week}</Text>
                {sessions.map((session) => {
                  const isActiveNow = session.status === 'active' && !isIdentityVerified;

                  return (
                    <View
                      key={session.id}
                      style={[
                        styles.sessionCard,
                        isActiveNow && styles.sessionCardActive,
                        (session.status === 'closed') && styles.sessionCardClosed,
                      ]}
                    >
                      <View style={styles.sessionCardHeader}>
                        <View style={styles.sessionCardLeft}>
                          <Text style={styles.sessionCardTitle}>{session.title}</Text>
                          <Text style={styles.sessionCardTime}>{session.timeText}</Text>
                        </View>
                        {renderBadge(session.status)}
                      </View>

                      {session.recordedTime && (
                        <Text style={styles.sessionRecordedText}>{session.recordedTime}</Text>
                      )}

                      {/* Render 'Start attendance' button only if session is active and not verified */}
                      {isActiveNow && (
                        <View style={styles.buttonContainer}>
                          <Pressable
                            style={({ pressed }) => [
                              styles.btnStart,
                              pressed && styles.btnStartPressed,
                            ]}
                          >
                            <Text style={styles.btnStartLabel}>Start attendance</Text>
                          </Pressable>
                        </View>
                      )}
                    </View>
                  );
                })}
              </View>
            ))}
          </View>
        ) : (
          <View>
            {/* Elevated Attendance Summary Card */}
            <View style={styles.elevatedCard}>
              <Text style={styles.attendancePercentageBig}>{course.attendancePercentage}%</Text>
              <Text style={styles.attendanceTarget}>Current attendance · Target 80%</Text>

              {/* Progress Bar */}
              <View style={styles.progressTrack}>
                <View
                  style={[
                    styles.progressFill,
                    { width: `${course.attendancePercentage}%` },
                  ]}
                />
              </View>

              {/* Stats Row */}
              <View style={styles.statsRow}>
                <View style={styles.statCol}>
                  <Text style={styles.statValue}>{course.totalSessions}</Text>
                  <Text style={styles.statLabel}>Completed</Text>
                </View>
                <View style={styles.statCol}>
                  <Text style={[styles.statValue, styles.statPresent]}>{course.attendedSessions}</Text>
                  <Text style={styles.statLabel}>Present</Text>
                </View>
                <View style={styles.statCol}>
                  <Text style={[styles.statValue, styles.statAbsent]}>
                    {course.totalSessions - course.attendedSessions}
                  </Text>
                  <Text style={styles.statLabel}>Absent</Text>
                </View>
              </View>
            </View>

            {/* Attendance Record Section */}
            <Text style={styles.hSection}>Attendance record</Text>
            <View style={styles.recordListCard}>
              {course.attendanceRecords.map((record, index) => (
                <View key={record.id}>
                  <View style={styles.sessionRow}>
                    {/* Date Column */}
                    <View style={styles.dateCol}>
                      <Text style={styles.dateDay}>{record.day}</Text>
                      <Text style={styles.dateMonth}>{record.month}</Text>
                    </View>

                    {/* Middle Details */}
                    <View style={styles.sessionRowDetails}>
                      <Text style={styles.sessionRowTitle}>{record.title}</Text>
                      <Text style={styles.sessionRowSubtext}>{record.recordedText}</Text>
                    </View>

                    {/* Right Badge */}
                    <View
                      style={[
                        styles.recordStatusBadge,
                        record.status === 'Present'
                          ? styles.recordStatusBadgePresent
                          : styles.recordStatusBadgeAbsent,
                      ]}
                    >
                      <SymbolView
                        name={
                          record.status === 'Present'
                            ? {
                                ios: 'checkmark.circle',
                                android: 'check_circle',
                                web: 'check_circle',
                              }
                            : {
                                ios: 'exclamationmark.circle',
                                android: 'error',
                                web: 'error',
                              }
                        }
                        size={14}
                        tintColor={
                          record.status === 'Present'
                            ? lightColors.success
                            : lightColors.error
                        }
                        style={styles.recordStatusIcon}
                      />
                      <Text
                        style={[
                          styles.recordStatusText,
                          record.status === 'Present'
                            ? styles.recordStatusTextPresent
                            : styles.recordStatusTextAbsent,
                        ]}
                      >
                        {record.status}
                      </Text>
                    </View>
                  </View>

                  {index < course.attendanceRecords.length - 1 && (
                    <View style={styles.rowDivider} />
                  )}
                </View>
              ))}
            </View>
          </View>
        )}
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorText: {
    ...typography.body,
    color: lightColors.error,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xxs,
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
  subheaderText: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginLeft: spacing.xxs,
    marginTop: -spacing.xxs,
    marginBottom: spacing.md,
  },
  segmentedContainer: {
    flexDirection: 'row',
    backgroundColor: lightColors.neutralBackground,
    borderRadius: radii.small,
    padding: 2,
    marginBottom: spacing.md,
  },
  segItem: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: radii.small - 2,
  },
  segItemActive: {
    backgroundColor: lightColors.surface,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 1.5,
    elevation: 1,
  },
  segItemText: {
    ...typography.supporting,
    fontWeight: '600',
    color: lightColors.textSecondary,
  },
  segItemTextActive: {
    color: lightColors.textPrimary,
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  dashedCard: {
    padding: spacing.md,
    backgroundColor: '#F9FAFB',
    borderRadius: radii.card,
    borderWidth: 1.5,
    borderColor: lightColors.border,
    borderStyle: 'dashed',
    marginBottom: spacing.md,
  },
  dashedCardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dashedCardLabel: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
  dashedCardValue: {
    ...typography.cardTitle,
    fontWeight: '800',
    color: lightColors.primaryInteraction,
  },
  dashedCardSubtext: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 4,
  },
  simulationHelper: {
    backgroundColor: lightColors.neutralBackground,
    paddingVertical: 10,
    borderRadius: radii.small,
    alignItems: 'center',
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
  },
  simulationHelperText: {
    ...typography.caption,
    fontWeight: '700',
    color: lightColors.primaryInteraction,
  },
  weekGroup: {
    marginBottom: spacing.md,
  },
  weekHead: {
    ...typography.supporting,
    fontWeight: '700',
    color: lightColors.textPrimary,
    marginBottom: spacing.xs,
    textTransform: 'none',
  },
  sessionCard: {
    backgroundColor: lightColors.surface,
    borderRadius: radii.card,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: lightColors.border,
    marginBottom: spacing.xs,
  },
  sessionCardActive: {
    backgroundColor: lightColors.primaryLight,
    borderColor: '#C3D2F5',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
  },
  sessionCardClosed: {
    opacity: 0.8,
  },
  sessionCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  sessionCardLeft: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  sessionCardTitle: {
    ...typography.cardTitle,
    color: lightColors.textPrimary,
  },
  sessionCardTime: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 4,
  },
  sessionRecordedText: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 8,
  },
  buttonContainer: {
    marginTop: spacing.sm,
    flexDirection: 'row',
  },
  btnStart: {
    backgroundColor: lightColors.primaryInteraction,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: radii.button - 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnStartPressed: {
    opacity: 0.8,
  },
  btnStartLabel: {
    ...typography.caption,
    fontWeight: '700',
    color: lightColors.surface,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radii.full,
  },
  badgeIcon: {
    marginRight: 4,
  },
  badgeText: {
    ...typography.caption,
    fontWeight: '700',
  },
  badgeActive: {
    backgroundColor: lightColors.successBackground,
  },
  badgeTextActive: {
    color: lightColors.success,
  },
  badgeWaiting: {
    backgroundColor: lightColors.primaryLight,
  },
  badgeTextWaiting: {
    color: '#1D4ED8',
  },
  badgeUpcoming: {
    backgroundColor: lightColors.neutralBackground,
  },
  badgeTextUpcoming: {
    color: lightColors.primary,
  },
  badgeMarked: {
    backgroundColor: lightColors.successBackground,
  },
  badgeTextMarked: {
    color: lightColors.success,
  },
  badgeMissed: {
    backgroundColor: lightColors.errorBackground,
  },
  badgeTextMissed: {
    color: lightColors.error,
  },
  badgeClosed: {
    backgroundColor: lightColors.neutralBackground,
  },
  badgeTextClosed: {
    color: lightColors.neutral,
  },
  elevatedCard: {
    backgroundColor: lightColors.surface,
    borderRadius: radii.card,
    padding: spacing.lg,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: lightColors.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
    marginBottom: spacing.lg,
  },
  attendancePercentageBig: {
    fontSize: 40,
    fontWeight: '800',
    color: lightColors.primaryInteraction,
    lineHeight: 44,
  },
  attendanceTarget: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 6,
  },
  progressTrack: {
    width: '100%',
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: radii.full,
    marginTop: spacing.md,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: lightColors.primaryInteraction,
    borderRadius: radii.full,
  },
  statsRow: {
    flexDirection: 'row',
    width: '100%',
    justifyContent: 'space-between',
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  statCol: {
    alignItems: 'center',
    flex: 1,
  },
  statValue: {
    fontSize: 16,
    fontWeight: '800',
    color: lightColors.textPrimary,
  },
  statPresent: {
    color: lightColors.success,
  },
  statAbsent: {
    color: lightColors.error,
  },
  statLabel: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 4,
  },
  hSection: {
    ...typography.sectionTitle,
    color: lightColors.textPrimary,
    marginBottom: spacing.sm,
  },
  recordListCard: {
    backgroundColor: lightColors.surface,
    borderRadius: radii.card,
    borderWidth: 1,
    borderColor: lightColors.border,
    overflow: 'hidden',
  },
  sessionRow: {
    flexDirection: 'row',
    padding: spacing.md,
    alignItems: 'center',
  },
  dateCol: {
    width: 44,
    height: 48,
    backgroundColor: '#F3F4F6',
    borderRadius: radii.small - 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  dateDay: {
    fontSize: 16,
    fontWeight: '800',
    color: lightColors.textPrimary,
    lineHeight: 18,
  },
  dateMonth: {
    ...typography.caption,
    color: lightColors.textSecondary,
    fontSize: 10,
    fontWeight: '700',
    lineHeight: 12,
  },
  sessionRowDetails: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  sessionRowTitle: {
    ...typography.body,
    fontWeight: '700',
    color: lightColors.textPrimary,
  },
  sessionRowSubtext: {
    ...typography.supporting,
    color: lightColors.textSecondary,
    marginTop: 3,
  },
  recordStatusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radii.full,
  },
  recordStatusBadgePresent: {
    backgroundColor: lightColors.successBackground,
  },
  recordStatusBadgeAbsent: {
    backgroundColor: lightColors.errorBackground,
  },
  recordStatusIcon: {
    marginRight: 4,
  },
  recordStatusText: {
    ...typography.caption,
    fontWeight: '700',
  },
  recordStatusTextPresent: {
    color: lightColors.success,
  },
  recordStatusTextAbsent: {
    color: lightColors.error,
  },
  rowDivider: {
    height: 1,
    backgroundColor: lightColors.border,
    marginLeft: 44 + spacing.md + spacing.md, // Align with details content
  },
});
