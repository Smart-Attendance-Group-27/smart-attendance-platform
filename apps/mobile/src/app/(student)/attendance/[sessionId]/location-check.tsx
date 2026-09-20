import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { getMockAttendance, markMockFacePassed, markMockGeofencePassed } from '../../../../features/attendance/__fixtures__/mockAttendanceStore';
import { LocationCheckScreen } from '../../../../features/location/screens/LocationCheckScreen';
import { CoreApiGeofenceValidationService } from '../../../../features/location/services/coreApiGeofenceValidationService';
import { ExpoLocationProvider } from '../../../../features/location/services/expoLocationProvider';
import { LiveLocationService } from '../../../../features/location/services/liveLocationService';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function LocationCheckRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const {
    sessionId: sessionIdParam,
  } = useLocalSearchParams<{
    sessionId?: string | string[];
  }>();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const locationService = useMemo(() => {
    if (process.env.EXPO_PUBLIC_API_MODE === 'mock') {
      return {
        async validateLocation(sessionId: string) {
          const state = markMockGeofencePassed(sessionId);
          if (!state) return { status: 'session_unavailable' as const };
          if (!state.requiresFaceVerification) {
            markMockFacePassed(sessionId);
            return { status: 'inside_geofence' as const,
              initialCheckIn: getMockAttendance(sessionId)?.initialCheckIn };
          }
          return { status: 'inside_geofence' as const, initialCheckIn: null };
        },
      };
    }
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
      onAlreadyCheckedIn={(completedSessionId) =>
        router.replace({
          pathname:
            '/(student)/attendance/[sessionId]/progress',
          params: { sessionId: completedSessionId },
        } as unknown as Href)
      }
      onLocationValidated={(validatedSessionId, initialCheckIn) =>
        router[initialCheckIn ? 'replace' : 'push']({
          pathname: initialCheckIn
            ? '/(student)/attendance/[sessionId]/progress'
            : '/(student)/attendance/[sessionId]/face-introduction',
          params: { sessionId: validatedSessionId },
        } as unknown as Href)
      }
      sessionId={sessionId}
    />
  );
}
