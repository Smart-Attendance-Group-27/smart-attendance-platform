import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { LocationCheckScreen } from '../../../../features/location/screens/LocationCheckScreen';
import { CoreApiGeofenceValidationService } from '../../../../features/location/services/coreApiGeofenceValidationService';
import { ExpoLocationProvider } from '../../../../features/location/services/expoLocationProvider';
import { LiveLocationService } from '../../../../features/location/services/liveLocationService';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function LocationCheckRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const { sessionId: sessionIdParam } = useLocalSearchParams<{
    sessionId?: string | string[];
  }>();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const locationService = useMemo(() => {
    const coreApiClient = new CoreApiClient({
      getAccessToken: () => accessToken,
    });

    return new LiveLocationService(
      new ExpoLocationProvider(),
      new CoreApiGeofenceValidationService(coreApiClient),
    );
  }, [accessToken]);
  const sessionIdValue = Array.isArray(sessionIdParam)
    ? sessionIdParam[0]
    : sessionIdParam;
  const sessionId = sessionIdValue?.trim();

  if (session.status !== 'authenticated') {
    return null;
  }

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
