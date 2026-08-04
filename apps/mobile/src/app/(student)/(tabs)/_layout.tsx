import { Tabs } from 'expo-router';
import { SymbolView } from 'expo-symbols';

import {
  lightColors,
  typography,
} from '../../../theme';

export default function StudentTabsLayout() {
  return (
    <Tabs
      backBehavior="initialRoute"
      initialRouteName="index"
      screenOptions={{
        tabBarItemStyle: {
          paddingVertical: 5,
        },
        headerShown: false,
        tabBarActiveTintColor: lightColors.primaryInteraction,
        tabBarInactiveTintColor: lightColors.textSecondary,
        tabBarHideOnKeyboard: true,
        tabBarLabelStyle: {
          ...typography.caption,
        },
        tabBarStyle: {
          height: 64,
          backgroundColor: lightColors.surface,
          borderTopColor: lightColors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          tabBarIcon: ({ color, size }) => (
            <SymbolView
              name={{ ios: 'house', android: 'home', web: 'home' }}
              size={size}
              tintColor={color}
            />
          ),
          title: 'Home',
        }}
      />

      <Tabs.Screen
        name="courses"
        options={{
          tabBarIcon: ({ color, size }) => (
            <SymbolView
              name={{ ios: 'book.closed', android: 'menu_book', web: 'menu_book' }}
              size={size}
              tintColor={color}
            />
          ),
          title: 'Courses',
        }}
      />

      <Tabs.Screen
        name="notifications"
        options={{
          tabBarIcon: ({ color, size }) => (
            <SymbolView
              name={{ ios: 'bell', android: 'notifications', web: 'notifications' }}
              size={size}
              tintColor={color}
            />
          ),
          title: 'Notifications',
        }}
      />
    </Tabs>
  );
}
