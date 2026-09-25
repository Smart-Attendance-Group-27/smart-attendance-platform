import type { PropsWithChildren } from 'react';
import {
  RefreshControlProps,
  ScrollView,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { lightColors, spacing } from '../../theme';

type ScreenContainerProps = PropsWithChildren<{
  scrollable?: boolean;
  contentContainerStyle?: StyleProp<ViewStyle>;
  refreshControl?: React.ReactElement<RefreshControlProps>;
}>;

export function ScreenContainer({
  children,
  scrollable = false,
  contentContainerStyle,
  refreshControl,
}: ScreenContainerProps) {
  return (
    <SafeAreaView style={styles.safeArea}>
      {scrollable ? (
        <ScrollView
          contentContainerStyle={[
            styles.contentContainer,
            styles.scrollContent,
            contentContainerStyle,
          ]}
          keyboardShouldPersistTaps="handled"
          refreshControl={refreshControl}
          showsVerticalScrollIndicator={false}
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.content, contentContainerStyle]}>
          {children}
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: lightColors.background,
  },

  content: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },

  contentContainer: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },

  scrollContent: {
    flexGrow: 1,
  },
});