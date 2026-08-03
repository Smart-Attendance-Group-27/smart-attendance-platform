import { Tabs } from 'expo-router';

import {
  lightColors,
  typography,
} from '../../../theme';

export default function StudentTabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: lightColors.primaryInteraction,
        tabBarInactiveTintColor: lightColors.textSecondary,
        tabBarHideOnKeyboard: true,
        tabBarLabelStyle: {
          ...typography.caption,
        },
        tabBarStyle: {
          backgroundColor: lightColors.surface,
          borderTopColor: lightColors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
        }}
      />

      <Tabs.Screen
        name="courses"
        options={{
          title: 'Courses',
        }}
      />

      <Tabs.Screen
        name="notifications"
        options={{
          title: 'Notifications',
        }}
      />
    </Tabs>
  );
}