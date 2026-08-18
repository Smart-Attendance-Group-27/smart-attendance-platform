import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { CheckInResultScreen } from '../../../../features/attendance/screens/CheckInResultScreen';
import { CoreApiAttendanceService } from '../../../../features/attendance/services/coreApiAttendanceService';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function CheckInSuccessRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const attendanceService = useMemo(
    () =>
      new CoreApiAttendanceService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );
  const { sessionId: sessionIdParam } = useLocalSearchParams<{
    sessionId?: string | string[];
  }>();
  const sessionIdValue = Array.isArray(sessionIdParam)
    ? sessionIdParam[0]
    : sessionIdParam;
  const sessionId = sessionIdValue?.trim();

  if (!sessionId) {
    return (
      <ScreenContainer>
        <Text>
          We could not open this attendance step because the session link is
          incomplete.
        </Text>
      </ScreenContainer>
    );
  }

  if (session.status !== 'authenticated') {
    return null;
  }

  return (
    <CheckInResultScreen
      attendanceService={attendanceService}
      onOpenQrScanner={() =>
        router.push({
          pathname: '/(student)/attendance/[sessionId]/qr-scanner',
          params: { sessionId },
        })
      }
      onReturnHome={() => router.replace('/(student)/(tabs)')}
      sessionId={sessionId}
    />
  );
}
