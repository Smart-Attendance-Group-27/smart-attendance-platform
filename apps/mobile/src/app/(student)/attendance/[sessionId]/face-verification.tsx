import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { FaceVerificationScreen } from '../../../../features/face-verification/screens/FaceVerificationScreen';
import { CoreApiAttendanceFaceVerificationService } from '../../../../features/face-verification/services/coreApiAttendanceFaceVerificationService';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function FaceVerificationRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const {
    sessionId: sessionIdParam,
    requiresQr: requiresQrParam,
  } = useLocalSearchParams<{
    sessionId?: string | string[];
    requiresQr?: string | string[];
  }>();
  const sessionIdValue = Array.isArray(sessionIdParam)
    ? sessionIdParam[0]
    : sessionIdParam;
  const sessionId = sessionIdValue?.trim();
  const requiresQrValue = Array.isArray(requiresQrParam)
    ? requiresQrParam[0]
    : requiresQrParam;
  const requiresQr = requiresQrValue === '1';
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const faceVerificationService = useMemo(
    () =>
      new CoreApiAttendanceFaceVerificationService(
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
      onFaceVerified={(verifiedSessionId) =>
        router.push(
          requiresQr
            ? {
                pathname:
                  '/(student)/attendance/[sessionId]/qr-scanner',
                params: { sessionId: verifiedSessionId },
              }
            : {
                pathname:
                  '/(student)/attendance/[sessionId]/check-in-success',
                params: { sessionId: verifiedSessionId },
              },
        )
      }
      sessionId={sessionId}
    />
  );
}
