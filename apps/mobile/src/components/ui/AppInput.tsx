import type { ReactNode } from 'react';
import {
  type StyleProp,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  type TextStyle,
  View,
  type ViewStyle,
} from 'react-native';

import {
  lightColors,
  radii,
  spacing,
  typography,
} from '../../theme';

type AppInputProps = Omit<TextInputProps, 'style'> & {
  label?: string;
  errorMessage?: string;
  helperText?: string;
  rightElement?: ReactNode;
  containerStyle?: StyleProp<ViewStyle>;
  inputContainerStyle?: StyleProp<ViewStyle>;
  style?: StyleProp<TextStyle>;
};

export function AppInput({
  label,
  errorMessage,
  helperText,
  rightElement,
  containerStyle,
  inputContainerStyle,
  style,
  editable = true,
  accessibilityLabel,
  placeholder,
  ...textInputProps
}: AppInputProps) {
  const hasError = Boolean(errorMessage);

  return (
    <View style={[styles.field, containerStyle]}>
      {label ? <Text style={styles.label}>{label}</Text> : null}

      <View
        style={[
          styles.inputContainer,
          hasError && styles.inputContainerError,
          !editable && styles.inputContainerDisabled,
          inputContainerStyle,
        ]}
      >
        <TextInput
          {...textInputProps}
          accessibilityLabel={
            accessibilityLabel ?? label ?? placeholder
          }
          editable={editable}
          placeholder={placeholder}
          placeholderTextColor={lightColors.textSecondary}
          style={[styles.input, style]}
        />

        {rightElement ? (
          <View style={styles.rightElement}>
            {rightElement}
          </View>
        ) : null}
      </View>

      {hasError ? (
        <Text style={styles.errorText}>{errorMessage}</Text>
      ) : helperText ? (
        <Text style={styles.helperText}>{helperText}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    width: '100%',
  },

  label: {
    ...typography.supporting,
    marginBottom: spacing.xs,
    fontWeight: '600',
    color: lightColors.textPrimary,
  },

  inputContainer: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    borderWidth: 1.5,
    borderColor: lightColors.border,
    borderRadius: radii.input,
    backgroundColor: lightColors.surface,
  },

  inputContainerError: {
    borderColor: lightColors.error,
    backgroundColor: lightColors.errorBackground,
  },

  inputContainerDisabled: {
    backgroundColor: lightColors.neutralBackground,
    opacity: 0.7,
  },

  input: {
    ...typography.body,
    flex: 1,
    paddingVertical: 0,
    color: lightColors.textPrimary,
  },

  rightElement: {
    marginLeft: spacing.xs,
  },

  helperText: {
    ...typography.caption,
    marginTop: spacing.xxs,
    color: lightColors.textSecondary,
  },

  errorText: {
    ...typography.caption,
    marginTop: spacing.xxs,
    color: lightColors.error,
  },
});