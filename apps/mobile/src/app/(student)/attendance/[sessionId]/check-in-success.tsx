import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { CheckInResultScreen } from '../../../../features/attendance/screens/CheckInResultScreen';
import { MockAttendanceService } from '../../../../features/attendance/services/mockAttendanceService';

const attendanceService = new MockAttendanceService();

export default function CheckInSuccessRoute() {
  const router = useRouter();
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
