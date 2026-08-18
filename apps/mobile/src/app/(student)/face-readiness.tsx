import { useMemo } from 'react';
import { useRouter } from 'expo-router';

import { useAuth } from '../../features/auth/context/AuthContext';
import { FaceVerificationScreen } from '../../features/face-verification/screens/FaceVerificationScreen';
import { FaceVerificationApiService } from '../../features/face-verification/services/faceVerificationApiService';
import type { FaceVerificationService } from '../../features/face-verification/services/faceVerificationService';

const readinessSessionId = 'readiness-check';

export default function FaceReadinessRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const apiService = useMemo(
    () =>
      new FaceVerificationApiService({
        getAccessToken: () => accessToken,
      }),
    [accessToken],
  );
  const cameraService = useMemo<FaceVerificationService>(
    () => ({
      verifyFace: ({ capture }) =>
        apiService.verifyReadiness(capture.uri),
    }),
    [apiService],
  );

  if (session.status !== 'authenticated') {
    return null;
  }

  return (
    <FaceVerificationScreen
      faceVerificationService={cameraService}
      mode="readiness"
      onBack={() => router.back()}
      onFaceVerified={() => router.back()}
      sessionId={readinessSessionId}
    />
  );
}
