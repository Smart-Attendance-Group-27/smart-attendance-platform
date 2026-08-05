import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { AttendanceSessionDetailsScreen } from '../../../../features/attendance/screens/AttendanceSessionDetailsScreen';
import { MockAttendanceService } from '../../../../features/attendance/services/mockAttendanceService';

const attendanceService = new MockAttendanceService();

export default function AttendanceSessionDetailsRoute() {
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
    <AttendanceSessionDetailsScreen
      attendanceService={attendanceService}
      onBack={() => router.back()}
      onStartCheckIn={() =>
        router.push({
          pathname:
            '/(student)/attendance/[sessionId]/location-check',
          params: { sessionId },
        })
      }
      sessionId={sessionId}
    />
  );
}
