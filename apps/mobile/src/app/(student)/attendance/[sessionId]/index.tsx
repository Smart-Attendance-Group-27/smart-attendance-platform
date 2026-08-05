import { useLocalSearchParams } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { AttendanceSessionDetailsScreen } from '../../../../features/attendance/screens/AttendanceSessionDetailsScreen';

export default function AttendanceSessionDetailsRoute() {
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

  return <AttendanceSessionDetailsScreen sessionId={sessionId} />;
}
