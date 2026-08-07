import { Redirect } from 'expo-router';

export default function AuthLogoutCallbackRoute() {
  return <Redirect href="/(auth)/login" />;
}
