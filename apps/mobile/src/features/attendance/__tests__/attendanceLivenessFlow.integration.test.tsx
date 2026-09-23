import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import AttendanceSessionDetailsRoute from '../../../app/(student)/attendance/[sessionId]';
import FaceIntroductionRoute from '../../../app/(student)/attendance/[sessionId]/face-introduction';
import FaceVerificationRoute from '../../../app/(student)/attendance/[sessionId]/face-verification';
import LocationCheckRoute from '../../../app/(student)/attendance/[sessionId]/location-check';
import AttendanceProgressRoute from '../../../app/(student)/attendance/[sessionId]/progress';
import {
  getMockAttendance,
  markMockGeofencePassed,
  resetMockAttendanceStore,
} from '../__fixtures__/mockAttendanceStore';
import type { LocationValidationResult } from '../../location/types/locationValidation';

const sessionId = 'attendance-session-active';
const mockBack = jest.fn();
const mockPush = jest.fn();
const mockReplace = jest.fn();
const incompleteFaceOutcomes: [
  outcome: 'liveness_failure' | 'face_mismatch',
  actionLabel: 'Return liveness rejection' | 'Return face mismatch',
][] = [
  ['liveness_failure', 'Return liveness rejection'],
  ['face_mismatch', 'Return face mismatch'],
];
let mockFaceOutcome: 'success' | 'liveness_failure' | 'face_mismatch';
let mockFaceRenderCount: number;
let mockLocationResult: LocationValidationResult;
let mockSearchParams: { sessionId?: string | string[] };

jest.mock('expo-router', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react');

  return {
    useFocusEffect: (callback: () => void | (() => void)) =>
      React.useEffect(callback, [callback]),
    useLocalSearchParams: () => mockSearchParams,
    useRouter: () => ({
      back: mockBack,
      push: mockPush,
      replace: mockReplace,
    }),
  };
});

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({
    session: {
      status: 'authenticated',
      userId: 'student-1',
      accessToken: 'test-access-token',
    },
  }),
}));

jest.mock('../../location/services/liveLocationService', () => ({
  LiveLocationService: class {
    async validateLocation() {
      return mockLocationResult;
    }
  },
}));

jest.mock('../../face-verification/screens/FaceVerificationScreen', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Pressable, Text } = require('react-native');

  return {
    FaceVerificationScreen: ({
      onFaceVerified,
      sessionId: verifiedSessionId,
    }: {
      onFaceVerified: (value: string) => void;
      sessionId: string;
    }) => {
      mockFaceRenderCount += 1;
      const label = mockFaceOutcome === 'success'
        ? 'Complete face and liveness verification'
        : mockFaceOutcome === 'liveness_failure'
          ? 'Return liveness rejection'
          : 'Return face mismatch';

      return (
        <Pressable
          accessibilityLabel={label}
          accessibilityRole="button"
          onPress={() => {
            if (mockFaceOutcome === 'success') {
              onFaceVerified(verifiedSessionId);
            }
          }}
        >
          <Text>{label}</Text>
        </Pressable>
      );
    },
  };
});

describe('attendance liveness workflow regression', () => {
  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_MODE = 'mock';
    resetMockAttendanceStore();
    mockBack.mockClear();
    mockPush.mockClear();
    mockReplace.mockClear();
    mockFaceOutcome = 'success';
    mockFaceRenderCount = 0;
    mockLocationResult = { status: 'inside_geofence' };
    mockSearchParams = { sessionId };
  });

  afterEach(() => {
    delete process.env.EXPO_PUBLIC_API_MODE;
  });

  test('keeps location before face and liveness, then completes initial check-in', async () => {
    const details = await render(<AttendanceSessionDetailsRoute />);
    await fireEvent.press(
      await details.findByRole('button', { name: 'Start attendance check-in' }),
    );
    expect(mockPush).toHaveBeenLastCalledWith({
      pathname: '/(student)/attendance/[sessionId]/location-check',
      params: { sessionId },
    });
    await details.unmount();

    const location = await render(<LocationCheckRoute />);
    await fireEvent.press(location.getByRole('button', {
      name: 'Allow location access and check classroom location',
    }));
    await fireEvent.press(await location.findByRole('button', {
      name: 'Continue to face verification',
    }));
    expect(mockPush).toHaveBeenLastCalledWith({
      pathname: '/(student)/attendance/[sessionId]/face-introduction',
      params: { sessionId },
    });
    await location.unmount();

    const introduction = await render(<FaceIntroductionRoute />);
    await fireEvent.press(await introduction.findByRole('button', {
      name: 'Begin face verification',
    }));
    expect(mockPush).toHaveBeenLastCalledWith({
      pathname: '/(student)/attendance/[sessionId]/face-verification',
      params: { sessionId },
    });
    await introduction.unmount();

    const verification = await render(<FaceVerificationRoute />);
    await fireEvent.press(verification.getByRole('button', {
      name: 'Complete face and liveness verification',
    }));
    expect(mockReplace).toHaveBeenLastCalledWith({
      pathname: '/(student)/attendance/[sessionId]/progress',
      params: { sessionId },
    });
    expect(getMockAttendance(sessionId)?.initialCheckIn).not.toBeNull();
    await verification.unmount();

    mockPush.mockClear();
    const progress = await render(<AttendanceProgressRoute />);
    expect(await progress.findByText('Initial check-in complete (on time)'))
      .toBeTruthy();
    expect(mockPush).not.toHaveBeenCalled();
    expect(mockFaceRenderCount).toBe(1);
  });

  test('does not continue to face verification when location fails', async () => {
    process.env.EXPO_PUBLIC_API_MODE = 'api';
    mockLocationResult = { status: 'outside_geofence' };
    const screen = await render(<LocationCheckRoute />);

    await fireEvent.press(screen.getByRole('button', {
      name: 'Allow location access and check classroom location',
    }));

    expect(await screen.findByText('Outside classroom area')).toBeTruthy();
    expect(mockPush).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
    expect(mockFaceRenderCount).toBe(0);
    expect(getMockAttendance(sessionId)?.initialCheckIn).toBeNull();
  });

  test.each(incompleteFaceOutcomes)(
    'does not complete initial check-in after %s',
    async (outcome, actionLabel) => {
      markMockGeofencePassed(sessionId);
      mockFaceOutcome = outcome;
      const screen = await render(<FaceVerificationRoute />);

      await fireEvent.press(screen.getByRole('button', { name: actionLabel }));

      expect(mockReplace).not.toHaveBeenCalled();
      expect(mockPush).not.toHaveBeenCalled();
      expect(getMockAttendance(sessionId)?.verification.geofenceStatus)
        .toBe('passed');
      expect(getMockAttendance(sessionId)?.initialCheckIn).toBeNull();
    },
  );
});
