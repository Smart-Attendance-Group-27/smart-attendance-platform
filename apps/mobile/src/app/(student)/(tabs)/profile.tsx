import { ProfileScreen } from '../../../features/profile/screens/ProfileScreen';
import { useAuth } from '../../../features/auth/context/AuthContext';

export default function StudentProfileRoute() {
  const { session, signOut } = useAuth();

  if (session.status !== 'authenticated') {
    return null;
  }

  return <ProfileScreen onSignOutPress={signOut} session={session} />;
}
