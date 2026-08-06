import { DashboardScreen } from '../../../features/dashboard/screens/DashboardScreen';
import { useAuth } from '../../../features/auth/context/AuthContext';

export default function StudentHomeRoute() {
  const { signOut } = useAuth();

  return <DashboardScreen onSignOutPress={signOut} />;
}
