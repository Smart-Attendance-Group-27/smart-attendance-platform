import { StatusBar } from 'expo-status-bar';
import { SymbolView } from 'expo-symbols';
import {
  Image,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppButton } from '../ui';
import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../theme';
import { UniversityBackdrop } from './UniversityBackdrop';

type StudentLoginScreenProps = {
  authErrorMessage?: string | null;
  isLoginAvailable: boolean;
  isLoading: boolean;
  onLoginPress: () => Promise<void>;
};

export function StudentLoginScreen({
  authErrorMessage,
  isLoginAvailable,
  isLoading,
  onLoginPress,
}: StudentLoginScreenProps) {
  const buttonIsLoading = isLoading || !isLoginAvailable;
  const loadingTitle = isLoginAvailable
    ? 'Opening secure login...'
    : 'Preparing secure login...';

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <UniversityBackdrop />

      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.card}>
            <View style={styles.brandBlock}>
              <View style={styles.brandMark}>
                <Image
                  accessibilityIgnoresInvertColors
                  source={require('../../../assets/Uni.jpg')}
                  style={styles.brandLogo}
                />
              </View>
              <Text style={styles.brandTitle}>UniAttend</Text>
              <Text style={styles.brandSubtitle}>
                Secure student attendance
              </Text>
            </View>

            {authErrorMessage ? (
              <View accessibilityRole="alert" style={styles.errorNotice}>
                <SymbolView
                  name={{
                    ios: 'exclamationmark.circle',
                    android: 'error',
                    web: 'error',
                  }}
                  size={21}
                  tintColor={lightColors.error}
                />
                <Text style={styles.errorNoticeText}>{authErrorMessage}</Text>
              </View>
            ) : null}

            <View style={styles.loginButton}>
              <AppButton
                disabled={!isLoginAvailable}
                leftIcon={
                  <SymbolView
                    name={{
                      ios: 'person.badge.key',
                      android: 'passkey',
                      web: 'passkey',
                    }}
                    size={21}
                    tintColor={lightColors.surface}
                  />
                }
                loading={buttonIsLoading}
                loadingTitle={loadingTitle}
                onPress={onLoginPress}
                title="Continue with university login"
              />
            </View>
          </View>

          <View style={styles.footer}>
            <Text style={styles.authorizedText}>
              Authorized university students only
            </Text>
            <Text style={styles.versionText}>Version 1.0.0</Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: lightColors.primary,
  },
  safeArea: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'flex-end',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xxl,
    paddingBottom: spacing.xxl + 2,
  },
  card: {
    paddingHorizontal: 22,
    paddingVertical: 26,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.65)',
    borderRadius: radii.card,
    backgroundColor: 'rgba(255,255,255,0.98)',
    shadowColor: lightColors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 20,
    elevation: 8,
  },
  brandBlock: {
    alignItems: 'center',
    marginBottom: spacing.lg - 2,
  },
  brandMark: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
    borderRadius: radii.card,
    backgroundColor: lightColors.surface,
    overflow: 'hidden',
  },
  brandLogo: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  brandTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: lightColors.primary,
  },
  brandSubtitle: {
    ...typography.supporting,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },
  errorNotice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginBottom: spacing.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radii.input,
    backgroundColor: lightColors.errorBackground,
  },
  errorNoticeText: {
    ...typography.supporting,
    flex: 1,
    color: lightColors.error,
  },
  loginButton: {
    marginTop: 6,
  },
  footer: {
    alignItems: 'center',
    marginTop: 18,
  },
  authorizedText: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.75)',
  },
  versionText: {
    marginTop: spacing.xxs,
    fontSize: 11,
    color: 'rgba(255,255,255,0.5)',
  },
});
