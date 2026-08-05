import { useEffect, useState } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

import { lightColors, radii, spacing } from '../../../theme';

const SKELETON_ROWS = 4;

export function NotificationListSkeleton() {
  const [opacity] = useState(() => new Animated.Value(0.55));

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          duration: 700,
          toValue: 1,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          duration: 700,
          toValue: 0.55,
          useNativeDriver: true,
        }),
      ]),
    );

    animation.start();
    return () => animation.stop();
  }, [opacity]);

  return (
    <View
      accessibilityLabel="Loading notifications"
      accessibilityRole="progressbar"
    >
      {Array.from({ length: SKELETON_ROWS }, (_, index) => (
        <View key={index} style={styles.row}>
          <Animated.View style={[styles.icon, { opacity }]} />
          <View style={styles.copy}>
            <Animated.View style={[styles.title, { opacity }]} />
            <Animated.View style={[styles.description, { opacity }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: lightColors.border,
  },
  icon: {
    width: 40,
    height: 40,
    flexShrink: 0,
    borderRadius: radii.small + 3,
    backgroundColor: lightColors.border,
  },
  copy: {
    flex: 1,
    paddingTop: 1,
  },
  title: {
    width: '80%',
    height: 13,
    marginBottom: spacing.xs,
    borderRadius: radii.small,
    backgroundColor: lightColors.border,
  },
  description: {
    width: '55%',
    height: 11,
    borderRadius: radii.small,
    backgroundColor: lightColors.border,
  },
});
