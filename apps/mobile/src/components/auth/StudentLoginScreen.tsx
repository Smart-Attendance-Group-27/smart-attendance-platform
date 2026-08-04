import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

import { AppButton, AppInput } from '../ui';
import { lightColors, radii, spacing, typography } from '../../theme';
import { UniversityBackdrop } from './UniversityBackdrop';

type StudentLoginScreenProps = {
  onMockLoginSuccess: () => void;
};

type FieldErrors = {
  username?: string;
  password?: string;
};

const MOCK_LOGIN_DELAY_MS = 800;

export function StudentLoginScreen({
  onMockLoginSuccess,
}: StudentLoginScreenProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async () => {
    const nextErrors: FieldErrors = {};

    if (!username.trim()) {
      nextErrors.username = 'University username is required';
    }
    if (!password) {
      nextErrors.password = 'Password is required';
    }

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    // Temporary local delay for the mock UI flow only. Real authentication
    // will replace this boundary in a future task.
    setIsLoading(true);
    await new Promise<void>((resolve) => {
      setTimeout(resolve, MOCK_LOGIN_DELAY_MS);
    });
    onMockLoginSuccess();
  };

  const clearFieldError = (field: keyof FieldErrors) => {
    if (!errors[field]) {
      return;
    }

    setErrors((currentErrors) => ({ ...currentErrors, [field]: undefined }));
  };

  const hasErrors = Boolean(errors.username || errors.password);

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <UniversityBackdrop />

      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardArea}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View style={styles.card}>
              <View style={styles.brandBlock}>
                <View style={styles.brandMark}>
                  <Text style={styles.brandMarkText}>U</Text>
                </View>
                <Text style={styles.brandTitle}>UniAttend</Text>
                <Text style={styles.brandSubtitle}>
                  Secure student attendance
                </Text>
              </View>

              {hasErrors ? (
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
                  <Text style={styles.errorNoticeText}>
                    Enter your username and password to continue.
                  </Text>
                </View>
              ) : null}

              <AppInput
                autoCapitalize="characters"
                autoComplete="username"
                containerStyle={styles.field}
                editable={!isLoading}
                errorMessage={errors.username}
                label="University username"
                onChangeText={(value) => {
                  setUsername(value);
                  clearFieldError('username');
                }}
                placeholder="e.g. 230736R"
                returnKeyType="next"
                value={username}
              />

              <AppInput
                autoCapitalize="none"
                autoComplete="password"
                containerStyle={styles.field}
                editable={!isLoading}
                errorMessage={errors.password}
                label="Password"
                onChangeText={(value) => {
                  setPassword(value);
                  clearFieldError('password');
                }}
                onSubmitEditing={handleLogin}
                placeholder="Enter your password"
                returnKeyType="done"
                rightElement={
                  <Pressable
                    accessibilityLabel={
                      passwordVisible ? 'Hide password' : 'Show password'
                    }
                    accessibilityRole="button"
                    hitSlop={10}
                    onPress={() => setPasswordVisible((visible) => !visible)}
                    style={({ pressed }) => [
                      styles.visibilityButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <SymbolView
                      name={
                        passwordVisible
                          ? { ios: 'eye', android: 'visibility', web: 'visibility' }
                          : {
                              ios: 'eye.slash',
                              android: 'visibility_off',
                              web: 'visibility_off',
                            }
                      }
                      size={22}
                      tintColor={lightColors.textSecondary}
                    />
                  </Pressable>
                }
                secureTextEntry={!passwordVisible}
                value={password}
              />

              <View style={styles.loginButton}>
                <AppButton
                  loading={isLoading}
                  loadingTitle="Signing in…"
                  onPress={handleLogin}
                  title="Log in"
                />
              </View>

              {!isLoading ? (
                <Pressable
                  accessibilityHint="Password recovery is not available yet"
                  accessibilityRole="button"
                  style={({ pressed }) => [
                    styles.forgotButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.forgotLabel}>Forgot password?</Text>
                </Pressable>
              ) : null}
            </View>

            <View style={styles.footer}>
              <Text style={styles.authorizedText}>
                Authorized university students only
              </Text>
              <Text style={styles.versionText}>Version 1.0.0</Text>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
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
  keyboardArea: {
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
    width: 56,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
    borderRadius: radii.card,
    backgroundColor: lightColors.primary,
  },
  brandMarkText: {
    fontSize: 24,
    fontWeight: '800',
    color: lightColors.surface,
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
  field: {
    marginBottom: spacing.md,
  },
  visibilityButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: -8,
    marginRight: -8,
  },
  loginButton: {
    marginTop: 6,
  },
  forgotButton: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.xs,
  },
  forgotLabel: {
    ...typography.body,
    fontWeight: '600',
    color: lightColors.primaryInteraction,
  },
  pressed: {
    opacity: 0.65,
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
