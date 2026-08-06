import { Redirect } from 'expo-router';
import {
  ActivityIndicator,
  StyleSheet,
  View,
} from 'react-native';

import { useAuth } from '../../features/auth/context/AuthContext';
import { lightColors } from '../../theme';

export default function AuthCallbackRoute() {
  const {
    isRestoring,
    isSigningIn,
    session,
  } = useAuth();

  if (session.status === 'authenticated') {
    return <Redirect href="/(student)/(tabs)" />;
  }

  if (!isRestoring && !isSigningIn) {
    return <Redirect href="/(auth)/login" />;
  }

  return (
    <View style={styles.screen}>
      <ActivityIndicator color={lightColors.primaryInteraction} size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: lightColors.background,
  },
});
