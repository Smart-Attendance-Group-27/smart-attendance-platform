import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { QrScannerScreen } from '../../../../features/qr/screens/QrScannerScreen';
import { CoreApiQrVerificationService } from '../../../../features/qr/services/coreApiQrVerificationService';

export default function QrScannerRoute() {
  const router = useRouter();
  const {
    qrSessionId: qrSessionIdParam,
    sessionId: sessionIdParam,
  } = useLocalSearchParams<{
    qrSessionId?: string | string[];
    sessionId?: string | string[];
  }>();
  const qrVerificationService = useMemo(
    () => new CoreApiQrVerificationService(),
    [],
  );
  const sessionIdValue = Array.isArray(sessionIdParam)
    ? sessionIdParam[0]
    : sessionIdParam;
  const sessionId = sessionIdValue?.trim();
  const qrSessionIdValue = Array.isArray(qrSessionIdParam)
    ? qrSessionIdParam[0]
    : qrSessionIdParam;
  const qrSessionId = qrSessionIdValue?.trim();

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
      qrSessionId={qrSessionId}
      qrVerificationService={qrVerificationService}
      sessionId={sessionId}
    />
  );
}
