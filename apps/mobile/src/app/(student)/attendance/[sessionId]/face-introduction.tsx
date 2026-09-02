import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { FaceIntroductionScreen } from '../../../../features/face-verification/screens/FaceIntroductionScreen';

export default function FaceIntroductionRoute() {
  const router = useRouter();
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
  const requiresQr = Array.isArray(requiresQrParam)
    ? requiresQrParam[0]
    : requiresQrParam;

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
    <FaceIntroductionScreen
      onBack={() => router.back()}
      onBeginVerification={(verifiedSessionId) =>
        router.push({
          pathname:
            '/(student)/attendance/[sessionId]/face-verification',
          params: { sessionId: verifiedSessionId, requiresQr },
        })
      }
      sessionId={sessionId}
    />
  );
}
