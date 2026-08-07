import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { QrScannerScreen } from '../../../../features/qr/screens/QrScannerScreen';

export default function QrScannerRoute() {
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
    <QrScannerScreen
      onBack={() => router.back()}
      onQrScanned={() => {
        // Verification API integration comes later; this route currently
        // proves that the scanner can decode the backend-generated qrValue.
      }}
      sessionId={sessionId}
    />
  );
}
