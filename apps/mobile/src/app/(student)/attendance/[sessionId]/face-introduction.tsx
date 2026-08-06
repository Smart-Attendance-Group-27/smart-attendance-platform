import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { FaceIntroductionScreen } from '../../../../features/face-verification/screens/FaceIntroductionScreen';

export default function FaceIntroductionRoute() {
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
    <FaceIntroductionScreen
      onBack={() => router.back()}
      onBeginVerification={(verifiedSessionId) =>
        router.push({
          pathname:
            '/(student)/attendance/[sessionId]/face-verification',
          params: { sessionId: verifiedSessionId },
        })
      }
      sessionId={sessionId}
    />
  );
}
