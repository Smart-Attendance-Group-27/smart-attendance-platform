import { Redirect, Stack } from 'expo-router'
import { ActivityIndicator, StyleSheet, View } from 'react-native'

import { useAuth } from '../../features/auth/context/AuthContext'
import {
  hasAuthRole,
  studentMobileRole,
} from '../../features/auth/utils/authRoles'
import { lightColors } from '../../theme'

export default function StudentLayout() {
  const { isRestoring, session } = useAuth()

  if (isRestoring) {
    return (
      <View style={styles.loadingScreen}>
        <ActivityIndicator color={lightColors.primaryInteraction} size="large" />
      </View>
    )
  }

  if (!hasAuthRole(session, studentMobileRole)) {
    return <Redirect href="/(auth)/login" />
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: 'slide_from_right',
      }}
    />
  )
}

const styles = StyleSheet.create({
  loadingScreen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: lightColors.background,
  },
})
