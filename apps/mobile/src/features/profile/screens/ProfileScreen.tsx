import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../../theme';
import type { AuthenticatedSession } from '../../auth/types/auth.types';
import type { ProfileService } from '../services/profile.service';
import type { StudentProfile } from '../types/profile.types';

type ProfileScreenProps = {
  readonly onSignOutPress: () => void | Promise<void>;
  readonly profileService: ProfileService;
  readonly session: AuthenticatedSession;
};

type ProfileScreenState =
  | { status: 'loading' }
  | { status: 'ready'; profile: StudentProfile }
  | { status: 'missing' }
  | { status: 'unauthenticated' }
  | { status: 'forbidden' }
  | { status: 'error' };

type StateMessageProps = {
  readonly action?: ReactNode;
  readonly icon: SymbolViewProps['name'];
  readonly message: string;
  readonly title: string;
};

export function ProfileScreen({
  onSignOutPress,
  profileService,
  session,
}: ProfileScreenProps) {
  const [screenState, setScreenState] = useState<ProfileScreenState>({
    status: 'loading',
  });
  const [requestNumber, setRequestNumber] = useState(0);

  useEffect(() => {
    let isMounted = true;

    profileService
      .getMyStudentProfile()
      .then((result) => {
        if (!isMounted) {
          return;
        }

        if (result.status === 'found') {
          setScreenState({ status: 'ready', profile: result.profile });
          return;
        }

        // Every other outcome is shown as itself. Mock data is never
        // substituted for a real failure.
        setScreenState({ status: toScreenStatus(result.status) });
      })
      .catch(() => {
        if (isMounted) {
          setScreenState({ status: 'error' });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [
    profileService,
    requestNumber,
  ]);

  const retry = useCallback(() => {
    setScreenState({ status: 'loading' });
    setRequestNumber((currentRequestNumber) => currentRequestNumber + 1);
  }, []);

  return (
    <ScreenContainer scrollable contentContainerStyle={styles.screen}>
      <View style={styles.header}>
        <Text accessibilityRole="header" style={styles.title}>
          Profile
        </Text>
        <Text style={styles.description}>
          Student identity and account details.
        </Text>
      </View>

      {screenState.status === 'loading' ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator
            accessible
            accessibilityLabel="Loading profile"
            accessibilityRole="progressbar"
            accessibilityState={{ busy: true }}
            color={lightColors.primaryInteraction}
            size="large"
          />
          <Text style={styles.loadingText}>Loading profile...</Text>
        </View>
      ) : null}

      {screenState.status === 'ready' ? (
        <ProfileContent
          onSignOutPress={onSignOutPress}
          profile={screenState.profile}
          session={session}
        />
      ) : null}

      {screenState.status === 'missing' ? (
        <StateMessage
          icon={{
            ios: 'person.crop.circle.badge.questionmark',
            android: 'account_circle',
            web: 'account_circle',
          }}
          message="No student profile is linked to this signed-in account yet."
          title="Profile not found"
        />
      ) : null}

      {screenState.status === 'unauthenticated' ? (
        <StateMessage
          action={(
            <View style={styles.stateAction}>
              <AppButton
                accessibilityLabel="Sign out and sign in again"
                onPress={() => void onSignOutPress()}
                title="Sign in again"
              />
            </View>
          )}
          icon={{
            ios: 'lock',
            android: 'lock',
            web: 'lock',
          }}
          message="Your session is no longer valid. Please sign in again."
          title="Session expired"
        />
      ) : null}

      {screenState.status === 'forbidden' ? (
        <StateMessage
          icon={{
            ios: 'hand.raised',
            android: 'block',
            web: 'block',
          }}
          message="This account does not have student access to UniAttend."
          title="Student access required"
        />
      ) : null}

      {screenState.status === 'error' ? (
        <StateMessage
          action={(
            <View style={styles.stateAction}>
              <AppButton
                accessibilityLabel="Retry loading profile"
                onPress={retry}
                title="Retry"
              />
            </View>
          )}
          icon={{
            ios: 'exclamationmark.triangle',
            android: 'warning',
            web: 'warning',
          }}
          message="The profile could not be loaded. Please try again."
          title="We couldn't load your profile"
        />
      ) : null}
    </ScreenContainer>
  );
}

function toScreenStatus(
  resultStatus: 'missing' | 'unauthenticated' | 'forbidden' | 'failed',
): 'missing' | 'unauthenticated' | 'forbidden' | 'error' {
  switch (resultStatus) {
    case 'missing':
      return 'missing';
    case 'unauthenticated':
      return 'unauthenticated';
    case 'forbidden':
      return 'forbidden';
    default:
      return 'error';
  }
}

function ProfileContent({
  onSignOutPress,
  profile,
  session,
}: {
  readonly onSignOutPress: () => void | Promise<void>;
  readonly profile: StudentProfile;
  readonly session: AuthenticatedSession;
}) {
  const initials = useMemo(() => getInitials(profile.fullName), [profile.fullName]);

  return (
    <View style={styles.content}>
      <View style={styles.identityPanel}>
        <View accessibilityLabel={`${profile.fullName} avatar`} style={styles.avatar}>
          <Text style={styles.avatarText}>{initials}</Text>
        </View>

        <View style={styles.identityText}>
          <Text style={styles.name}>{profile.fullName}</Text>
          <Text style={styles.registration}>{profile.registrationNumber}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Student details</Text>
        <View style={styles.detailsPanel}>
          <DetailRow
            icon={{
              ios: 'envelope',
              android: 'mail',
              web: 'mail',
            }}
            label="University email"
            value={profile.universityEmail}
          />
          <DetailRow
            icon={{
              ios: 'number',
              android: 'badge',
              web: 'badge',
            }}
            label="Registration number"
            value={profile.registrationNumber}
          />
          <DetailRow
            icon={{
              ios: 'person.text.rectangle',
              android: 'verified_user',
              web: 'verified_user',
            }}
            label="Keycloak user ID"
            value={session.userId}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        <Pressable
          accessibilityLabel="Sign out of UniAttend"
          accessibilityRole="button"
          onPress={() => void onSignOutPress()}
          style={({ pressed }) => [
            styles.signOutButton,
            pressed && styles.pressed,
          ]}
        >
          <SymbolView
            name={{
              ios: 'rectangle.portrait.and.arrow.right',
              android: 'logout',
              web: 'logout',
            }}
            size={20}
            tintColor={lightColors.error}
          />
          <Text style={styles.signOutLabel}>Sign out</Text>
        </Pressable>
      </View>
    </View>
  );
}

function DetailRow({
  icon,
  label,
  value,
}: {
  readonly icon: SymbolViewProps['name'];
  readonly label: string;
  readonly value: string;
}) {
  return (
    <View style={styles.detailRow}>
      <View style={styles.detailIcon}>
        <SymbolView
          name={icon}
          size={18}
          tintColor={lightColors.primaryInteraction}
        />
      </View>
      <View style={styles.detailText}>
        <Text style={styles.detailLabel}>{label}</Text>
        <Text style={styles.detailValue}>{value}</Text>
      </View>
    </View>
  );
}

function StateMessage({
  action,
  icon,
  message,
  title,
}: StateMessageProps) {
  return (
    <View style={styles.stateContainer}>
      <View style={styles.stateIcon}>
        <SymbolView
          name={icon}
          size={30}
          tintColor={lightColors.neutral}
        />
      </View>
      <Text accessibilityRole="header" style={styles.stateTitle}>
        {title}
      </Text>
      <Text style={styles.stateMessage}>{message}</Text>
      {action}
    </View>
  );
}

function getInitials(fullName: string) {
  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((namePart) => namePart[0]?.toUpperCase() ?? '')
    .join('');
}

const styles = StyleSheet.create({
  screen: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xxl,
  },
  header: {
    marginBottom: spacing.lg,
  },
  title: {
    ...typography.screenTitle,
    color: lightColors.textPrimary,
  },
  description: {
    ...typography.body,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
  loadingContainer: {
    flex: 1,
    minHeight: 360,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    ...typography.body,
    marginTop: spacing.sm,
    color: lightColors.textSecondary,
  },
  content: {
    gap: spacing.xl,
  },
  identityPanel: {
    minHeight: 132,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.small,
    backgroundColor: lightColors.surface,
  },
  avatar: {
    width: 72,
    height: 72,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.primaryLight,
  },
  avatarText: {
    fontSize: 24,
    lineHeight: 30,
    fontWeight: '800',
    color: lightColors.primary,
  },
  identityText: {
    flex: 1,
    minWidth: 0,
  },
  name: {
    ...typography.sectionTitle,
    color: lightColors.textPrimary,
  },
  registration: {
    ...typography.body,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    ...typography.sectionTitle,
    color: lightColors.textPrimary,
  },
  detailsPanel: {
    borderWidth: 1,
    borderColor: lightColors.border,
    borderRadius: radii.small,
    backgroundColor: lightColors.surface,
  },
  detailRow: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: lightColors.border,
  },
  detailIcon: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.infoBackground,
  },
  detailText: {
    flex: 1,
    minWidth: 0,
  },
  detailLabel: {
    ...typography.supporting,
    color: lightColors.textSecondary,
  },
  detailValue: {
    ...typography.body,
    marginTop: 2,
    color: lightColors.textPrimary,
  },
  signOutButton: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderWidth: 1.5,
    borderColor: lightColors.error,
    borderRadius: radii.button,
    backgroundColor: lightColors.surface,
  },
  signOutLabel: {
    ...typography.button,
    color: lightColors.error,
  },
  pressed: {
    opacity: 0.75,
  },
  stateContainer: {
    flex: 1,
    minHeight: 360,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
  },
  stateIcon: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.full,
    backgroundColor: lightColors.neutralBackground,
  },
  stateTitle: {
    ...typography.sectionTitle,
    marginTop: spacing.md,
    textAlign: 'center',
    color: lightColors.textPrimary,
  },
  stateMessage: {
    ...typography.body,
    maxWidth: 300,
    marginTop: spacing.xs,
    textAlign: 'center',
    color: lightColors.textSecondary,
  },
  stateAction: {
    width: '100%',
    marginTop: spacing.lg,
  },
});
