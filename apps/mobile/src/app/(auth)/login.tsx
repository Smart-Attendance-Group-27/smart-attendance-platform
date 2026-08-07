import { Redirect } from 'expo-router';

import { StudentLoginScreen } from '../../components/auth';
import { useAuth } from '../../features/auth/context/AuthContext';

export default function LoginRoute() {
  const {
    errorMessage,
    isAuthRequestReady,
    isRestoring,
    isSigningIn,
    session,
    signIn,
  } = useAuth();

  if (!isRestoring && session.status === 'authenticated') {
    return <Redirect href="/(student)/(tabs)" />;
  }

  return (
    <StudentLoginScreen
      authErrorMessage={errorMessage}
      isLoginAvailable={isAuthRequestReady}
      isLoading={isRestoring || isSigningIn}
      onLoginPress={signIn}
    />
  );
}
