import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { LocationCheckScreen } from '../../../../features/location/screens/LocationCheckScreen';
import { MockLocationService } from '../../../../features/location/services/mockLocationService';

const locationService = new MockLocationService({
  result: { status: 'inside_geofence' },
});

export default function LocationCheckRoute() {
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
    <LocationCheckScreen
      locationService={locationService}
      onBack={() => router.back()}
      onLocationValidated={(validatedSessionId) =>
        router.push({
          pathname:
            '/(student)/attendance/[sessionId]/face-introduction',
          params: { sessionId: validatedSessionId },
        })
      }
      sessionId={sessionId}
    />
  );
}
