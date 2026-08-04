import { useRouter } from 'expo-router';

import { StudentLoginScreen } from '../../components/auth';

export default function LoginRoute() {
  const router = useRouter();

  return (
    <StudentLoginScreen
      onMockLoginSuccess={() =>
        router.replace('/(student)/(tabs)', { withAnchor: true })
      }
    />
  );
}
