import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { QrScannerScreen } from '../../../../features/qr/screens/QrScannerScreen';
import { createQrVerificationService } from '../../../../features/qr/services/createQrServices';
import { CoreApiClient } from '../../../../services/api/coreApiClient';

export default function QrScannerRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const {
    qrSessionId: qrSessionIdParam,
    sessionId: sessionIdParam,
  } = useLocalSearchParams<{
    qrSessionId?: string | string[];
    sessionId?: string | string[];
  }>();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const qrVerificationService = useMemo(() => {
    const coreApiClient = new CoreApiClient({
      getAccessToken: () => accessToken,
    });

    return createQrVerificationService(coreApiClient);
  }, [accessToken]);
  const sessionIdValue = Array.isArray(sessionIdParam)
    ? sessionIdParam[0]
    : sessionIdParam;
  const sessionId = sessionIdValue?.trim();
  const qrSessionIdValue = Array.isArray(qrSessionIdParam)
    ? qrSessionIdParam[0]
    : qrSessionIdParam;
  const qrSessionId = qrSessionIdValue?.trim();

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
    <QrScannerScreen
      onBack={() => router.back()}
      onQrVerified={() => router.dismissTo({
        pathname: '/(student)/attendance/[sessionId]/progress', params: { sessionId },
      } as unknown as Href)}
      qrSessionId={qrSessionId}
      qrVerificationService={qrVerificationService}
      sessionId={sessionId}
    />
  );
}
