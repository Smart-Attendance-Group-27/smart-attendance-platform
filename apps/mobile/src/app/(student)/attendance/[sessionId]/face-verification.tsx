import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { FaceVerificationScreen } from '../../../../features/face-verification/screens/FaceVerificationScreen';
import { MockFaceVerificationService } from '../../../../features/face-verification/services/mockFaceVerificationService';

const faceVerificationService = new MockFaceVerificationService({
  result: { status: 'success' },
  delayMs: 750,
});

export default function FaceVerificationRoute() {
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
    <FaceVerificationScreen
      faceVerificationService={faceVerificationService}
      key={sessionId}
      onBack={() => router.back()}
      onFaceVerified={(verifiedSessionId) =>
        router.push({
          pathname:
            '/(student)/attendance/[sessionId]/qr-scanner',
          params: { sessionId: verifiedSessionId },
        })
      }
      sessionId={sessionId}
    />
  );
}
