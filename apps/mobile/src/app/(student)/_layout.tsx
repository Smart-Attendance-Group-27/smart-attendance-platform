import { useEffect, useRef } from 'react'
import * as Notifications from 'expo-notifications'
import { Redirect, Stack, useRouter } from 'expo-router'
import { ActivityIndicator, StyleSheet, View } from 'react-native'

import { useAuth } from '../../features/auth/context/AuthContext'
import { listenForPushTokenChanges, registerForPushNotifications, resetPushRegistrationStatus } from '../../features/notifications/services/pushNotificationService'
import { installNotificationNavigation } from '../../features/notifications/services/notificationNavigation'
import { notifyNotificationChanges } from '../../features/notifications/services/notificationEvents'
import { CoreApiClient, resolveCoreApiBaseUrl } from '../../services/api/coreApiClient'
import { lightColors } from '../../theme'

export default function StudentLayout() {
  const { isRestoring, session } = useAuth()
  const router = useRouter()
  const registeredUserId = useRef<string | null>(null)
  const accessToken = session.status === 'authenticated' ? session.accessToken : undefined

  useEffect(() => {
    if (session.status !== 'authenticated') {
      return undefined
    }
    const removeNavigation = installNotificationNavigation(
      (destination) => router.push(destination),
      Notifications,
    )
    const received = Notifications.addNotificationReceivedListener(
      () => notifyNotificationChanges(),
    )
    return () => {
      removeNavigation()
      received.remove()
    }
  }, [router, session.status])

  // Register device push token once after the student authenticates.
  // Fire-and-forget: a registration failure never blocks navigation.
  useEffect(() => {
    if (session.status !== 'authenticated') {
      registeredUserId.current = null
      resetPushRegistrationStatus()
      return
    }
    if (registeredUserId.current === session.userId) return
    registeredUserId.current = session.userId

    const accessToken = session.accessToken
    const apiClient = new CoreApiClient({
      baseUrl: resolveCoreApiBaseUrl(),
      getAccessToken: () => accessToken,
    })

    void registerForPushNotifications(apiClient)
  }, [session])

  useEffect(() => {
    if (!accessToken) return undefined
    const apiClient = new CoreApiClient({ getAccessToken: () => accessToken })
    return listenForPushTokenChanges(apiClient)
  }, [accessToken])

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
