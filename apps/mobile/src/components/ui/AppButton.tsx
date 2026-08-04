import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  type PressableProps,
  type StyleProp,
  StyleSheet,
  Text,
  type ViewStyle,
} from 'react-native';

import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../theme';

type AppButtonVariant =
  | 'primary'
  | 'secondary'
  | 'danger'
  | 'text';

type AppButtonProps = Omit<
  PressableProps,
  'children' | 'style'
> & {
  title: string;
  variant?: AppButtonVariant;
  loading?: boolean;
  loadingTitle?: string;
  fullWidth?: boolean;
  leftIcon?: ReactNode;
  style?: StyleProp<ViewStyle>;
};

export function AppButton({
  title,
  variant = 'primary',
  loading = false,
  loadingTitle,
  fullWidth = true,
  leftIcon,
  disabled = false,
  style,
  accessibilityLabel,
  ...pressableProps
}: AppButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <Pressable
      {...pressableProps}
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityRole="button"
      accessibilityState={{
        busy: loading,
        disabled: isDisabled,
      }}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        variantContainerStyles[variant],
        fullWidth && styles.fullWidth,
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator
          color={loadingIndicatorColors[variant]}
          size="small"
        />
      ) : leftIcon}

      <Text
        style={[
          styles.label,
          variantTextStyles[variant],
        ]}
      >
        {loading ? loadingTitle ?? title : title}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    borderWidth: 1.5,
    borderRadius: radii.button,
  },

  fullWidth: {
    width: '100%',
  },

  primary: {
    borderColor: lightColors.primaryInteraction,
    backgroundColor: lightColors.primaryInteraction,
  },

  secondary: {
    borderColor: lightColors.primaryInteraction,
    backgroundColor: 'transparent',
  },

  danger: {
    borderColor: lightColors.error,
    backgroundColor: lightColors.error,
  },

  text: {
    minHeight: 44,
    borderColor: 'transparent',
    backgroundColor: 'transparent',
  },

  pressed: {
    opacity: 0.8,
  },

  disabled: {
    opacity: 0.5,
  },

  label: {
    ...typography.button,
    textAlign: 'center',
  },

  primaryLabel: {
    color: lightColors.surface,
  },

  secondaryLabel: {
    color: lightColors.primaryInteraction,
  },

  dangerLabel: {
    color: lightColors.surface,
  },

  textLabel: {
    color: lightColors.primaryInteraction,
  },
});

const variantContainerStyles = {
  primary: styles.primary,
  secondary: styles.secondary,
  danger: styles.danger,
  text: styles.text,
} as const;

const variantTextStyles = {
  primary: styles.primaryLabel,
  secondary: styles.secondaryLabel,
  danger: styles.dangerLabel,
  text: styles.textLabel,
} as const;

const loadingIndicatorColors = {
  primary: lightColors.surface,
  secondary: lightColors.primaryInteraction,
  danger: lightColors.surface,
  text: lightColors.primaryInteraction,
} as const;
