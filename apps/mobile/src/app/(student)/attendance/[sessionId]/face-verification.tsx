import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { FaceVerificationScreen } from '../../../../features/face-verification/screens/FaceVerificationScreen';
import { MockFaceVerificationService } from '../../../../features/face-verification/services/mockFaceVerificationService';
import { markMockFacePassed } from '../../../../features/attendance/__fixtures__/mockAttendanceStore';
import { CoreApiAttendanceFaceVerificationService } from '../../../../features/face-verification/services/coreApiAttendanceFaceVerificationService';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function FaceVerificationRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const {
    sessionId: sessionIdParam,
  } = useLocalSearchParams<{
    sessionId?: string | string[];
  }>();
  const sessionIdValue = Array.isArray(sessionIdParam)
    ? sessionIdParam[0]
    : sessionIdParam;
  const sessionId = sessionIdValue?.trim();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const faceVerificationService = useMemo(
    () => process.env.EXPO_PUBLIC_API_MODE === 'mock'
      ? new MockFaceVerificationService({ result: { status: 'success' } })
      : new CoreApiAttendanceFaceVerificationService(
        new CoreApiClient({
          getAccessToken: () => accessToken,
          timeoutMs: 30_000,
        }),
    ),
    [accessToken],
  );

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
    <FaceVerificationScreen
      faceVerificationService={faceVerificationService}
      key={sessionId}
      onBack={() => router.back()}
      onFaceVerified={(verifiedSessionId) => {
        if (process.env.EXPO_PUBLIC_API_MODE === 'mock') markMockFacePassed(verifiedSessionId);
        router.replace({
          pathname: '/(student)/attendance/[sessionId]/progress',
          params: { sessionId: verifiedSessionId },
        } as unknown as Href);
      }}
      sessionId={sessionId}
    />
  );
}
