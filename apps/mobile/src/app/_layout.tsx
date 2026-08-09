import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar'; //syste controlled area at the top of the phone containing current time,network status,battery level
import { useCallback } from 'react';
import {
  StyleSheet,
  View,
} from 'react-native';
import {SafeAreaProvider} from 'react-native-safe-area-context';  //allows components such as our ScreenContainer to determine the safe visible area of the device

import { AuthProvider } from '../features/auth/context/AuthContext';

export default function RootLayout() {
  const handleRootLayout = useCallback(() => {
    void SplashScreen.hideAsync().catch(() => undefined);
  }, []);

  return (
    <View onLayout={handleRootLayout} style={styles.root}>
      <SafeAreaProvider>
        <AuthProvider>
          <StatusBar style='dark' />
          <Stack
            screenOptions={{
              headerShown: false
            }}
          />
        </AuthProvider>
      </SafeAreaProvider>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
});

//this file defines the navigation and shared structure around the routes inside the same folder
