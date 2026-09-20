import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { FaceIntroductionScreen } from '../../../../features/face-verification/screens/FaceIntroductionScreen';
import { CoreApiAttendanceFaceVerificationService } from '../../../../features/face-verification/services/coreApiAttendanceFaceVerificationService';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function FaceIntroductionRoute() {
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
    () =>
      new CoreApiAttendanceFaceVerificationService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );
  const [checkingProgress, setCheckingProgress] = useState(true);

  useEffect(() => {
    if (session.status !== 'authenticated' || !sessionId) {
      return;
    }

    let active = true;
    void (process.env.EXPO_PUBLIC_API_MODE === 'mock'
      ? Promise.resolve('required' as const)
      : faceVerificationService.getProgress(sessionId)).then((progress) => {
      if (!active) {
        return;
      }

      if (progress === 'passed') {
        router.replace({
          pathname: '/(student)/attendance/[sessionId]/progress',
          params: { sessionId },
        } as unknown as Href);
        return;
      }

      setCheckingProgress(false);
    });

    return () => {
      active = false;
    };
  }, [
    faceVerificationService,
    router,
    session.status,
    sessionId,
  ]);

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

  if (checkingProgress) {
    return (
      <ScreenContainer>
        <ActivityIndicator accessibilityLabel="Checking face verification status" />
        <Text>Checking face verification status...</Text>
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
