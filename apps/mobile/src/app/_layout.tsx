import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar'; //syste controlled area at the top of the phone containing current time,network status,battery level
import {SafeAreaProvider} from 'react-native-safe-area-context';  //allows components such as our ScreenContainer to determine the safe visible area of the device

import { AuthProvider } from '../features/auth/context/AuthContext';

export default function RootLayout() {
  return (
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
  )
}

//this file defines the navigation and shared structure around the routes inside the same folder
