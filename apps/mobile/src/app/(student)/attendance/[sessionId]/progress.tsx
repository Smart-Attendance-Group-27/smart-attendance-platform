import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { useMemo } from 'react';
import { Text } from 'react-native';

import { ScreenContainer } from '../../../../components/ui';
import { AttendanceProgressScreen } from '../../../../features/attendance/screens/AttendanceProgressScreen';
import { createAttendanceServices } from '../../../../features/attendance/services/createAttendanceServices';
import { useAuth } from '../../../../features/auth/context/AuthContext';
import { CoreApiClient } from '../../../../services/api/coreApiClient';
import { createQrProgressService } from '../../../../features/qr/services/createQrServices';

export default function AttendanceProgressRoute() {
  const router = useRouter();
  const { session } = useAuth();
  const { sessionId: value } = useLocalSearchParams<{ sessionId?: string | string[] }>();
  const sessionId = (Array.isArray(value) ? value[0] : value)?.trim();
  const accessToken = session.status === 'authenticated' ? session.accessToken : undefined;
  const attendanceService = useMemo(() => createAttendanceServices(
    new CoreApiClient({ getAccessToken: () => accessToken }),
  ), [accessToken]);
  const qrProgressService = useMemo(() => createQrProgressService(
    new CoreApiClient({ getAccessToken: () => accessToken }),
  ), [accessToken]);

  if (session.status !== 'authenticated') return null;
  if (!sessionId) return <ScreenContainer><Text>Attendance session link is incomplete.</Text></ScreenContainer>;

  return <AttendanceProgressScreen
    attendanceService={attendanceService}
    onOpenQrScanner={(qrSessionId) => router.push({
      pathname: '/(student)/attendance/[sessionId]/qr-scanner', params: { sessionId, qrSessionId },
    } as Href)}
    onReturnHome={() => router.replace('/(student)/(tabs)')}
    onStartCheckIn={() => router.push({
      pathname: '/(student)/attendance/[sessionId]/location-check', params: { sessionId },
    })}
    qrProgressService={qrProgressService}
    sessionId={sessionId}
  />;
}
