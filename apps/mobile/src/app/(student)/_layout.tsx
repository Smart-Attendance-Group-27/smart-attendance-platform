import { useEffect, useRef } from 'react'
import * as Notifications from 'expo-notifications'
import { Redirect, Stack, useRouter } from 'expo-router'
import { ActivityIndicator, StyleSheet, View } from 'react-native'

import { useAuth } from '../../features/auth/context/AuthContext'
import { registerForPushNotifications } from '../../features/notifications/services/pushNotificationService'
import { CoreApiClient, resolveCoreApiBaseUrl } from '../../services/api/coreApiClient'
import { lightColors } from '../../theme'

export default function StudentLayout() {
  const { isRestoring, session } = useAuth()
  const router = useRouter()
  const hasRegistered = useRef(false)

  // Listen for user tapping on a push notification
  useEffect(() => {
    const subscription = Notifications.addNotificationResponseReceivedListener(() => {
      router.push('/(student)/(tabs)/notifications')
    })
    return () => subscription.remove()
  }, [router])

  // Register device push token once after the student authenticates.
  // Fire-and-forget: a registration failure never blocks navigation.
  useEffect(() => {
    if (session.status !== 'authenticated' || hasRegistered.current) {
      return
    }
    hasRegistered.current = true

    const accessToken = session.accessToken
    const apiClient = new CoreApiClient({
      baseUrl: resolveCoreApiBaseUrl(),
      getAccessToken: () => accessToken,
    })

    void registerForPushNotifications(apiClient)
  }, [session])

  if (isRestoring) {
    return (
      <View style={styles.loadingScreen}>
        <ActivityIndicator color={lightColors.primaryInteraction} size="large" />
      </View>
    )
  }

  if (session.status !== 'authenticated') {
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
