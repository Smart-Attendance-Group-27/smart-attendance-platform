import {
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import {
  fireEvent,
  render,
} from '@testing-library/react-native';

import { AttendanceSessionDetailsScreen } from '../screens/AttendanceSessionDetailsScreen';
import type { AttendanceService } from '../services/attendanceService';
import { MockAttendanceService } from '../services/mockAttendanceService';

type ScreenTestProps = {
  sessionId: string;
  attendanceService: AttendanceService;
  onBack: () => void;
  onStartCheckIn: () => void;
};

function renderScreen(props: ScreenTestProps) {
  return render(<AttendanceSessionDetailsScreen {...props} />);
}

function createScreenProps(
  attendanceService: AttendanceService,
): ScreenTestProps {
  return {
    sessionId: 'attendance-session-active',
    attendanceService,
    onBack: jest.fn(),
    onStartCheckIn: jest.fn(),
  };
}

describe('AttendanceSessionDetailsScreen', () => {
  test('shows an accessible loading state without an enabled start action', async () => {
    const pendingService: AttendanceService = {
      getAttendanceSession: () => new Promise(() => undefined),
    };

    const { getByRole, queryByRole } = await renderScreen(
      createScreenProps(pendingService),
    );

    const loadingIndicator = getByRole('progressbar', {
      name: 'Loading attendance session',
    });

    expect(loadingIndicator.props.accessibilityState).toEqual(
      expect.objectContaining({ busy: true }),
    );
    expect(
      queryByRole('button', {
        name: 'Start attendance check-in',
      }),
    ).toBeNull();
  });

  test('shows active session information and the check-in window', async () => {
    const { findByText, getByRole, getByText } = await renderScreen(
      createScreenProps(new MockAttendanceService()),
    );

    await findByText(/CS3203/);

    expect(getByText(/Software Engineering Project/)).toBeTruthy();
    expect(getByText('Architecture Review Lecture')).toBeTruthy();
    expect(getByText(/Dr\. N\. Perera/)).toBeTruthy();
    expect(getByText(/10:00.*12:00/)).toBeTruthy();
    expect(getByText('Level 3 Lab')).toBeTruthy();
    expect(getByText('Lecture')).toBeTruthy();
    expect(getByText(/Check-in window: 09:50.*10:20/)).toBeTruthy();
    expect(
      getByText('Arrivals after 10:10 will be marked late.'),
    ).toBeTruthy();

    const startButton = getByRole('button', {
      name: 'Start attendance check-in',
    });

    expect(startButton.props.accessibilityState).toEqual(
      expect.objectContaining({ disabled: false }),
    );
  });

  test('invokes the supplied location-check callback for an active session', async () => {
    const props = createScreenProps(new MockAttendanceService());
    const { findByRole } = await renderScreen(props);

    const startButton = await findByRole('button', {
      name: 'Start attendance check-in',
    });

    fireEvent.press(startButton);

    expect(props.onStartCheckIn).toHaveBeenCalledTimes(1);
  });

  test('keeps a closed session read-only', async () => {
    const props: ScreenTestProps = {
      ...createScreenProps(new MockAttendanceService()),
      sessionId: 'attendance-session-closed',
    };
    const {
      findByText,
      getByText,
      queryByRole,
    } = await renderScreen(props);

    await findByText(/CS3052/);

    expect(getByText('Network Defence Lab')).toBeTruthy();
    expect(getByText('Level 2 Security Lab')).toBeTruthy();
    expect(
      getByText('This attendance session has ended. Details are read-only.'),
    ).toBeTruthy();

    const startButton = queryByRole('button', {
      name: 'Start attendance check-in',
    });

    if (startButton) {
      expect(startButton.props.accessibilityState).toEqual(
        expect.objectContaining({ disabled: true }),
      );
      fireEvent.press(startButton);
    }

    expect(props.onStartCheckIn).not.toHaveBeenCalled();
  });

  test('shows an unavailable state without fake session information', async () => {
    const props: ScreenTestProps = {
      ...createScreenProps(new MockAttendanceService()),
      sessionId: 'attendance-session-unavailable',
    };
    const {
      findByText,
      getByRole,
      queryByRole,
      queryByText,
    } = await renderScreen(props);

    await findByText('Session unavailable');

    expect(
      queryByText(/CS3203|Software Engineering Project/),
    ).toBeNull();
    expect(
      queryByRole('button', {
        name: 'Start attendance check-in',
      }),
    ).toBeNull();
    expect(
      getByRole('button', {
        name: 'Go back',
      }),
    ).toBeTruthy();
  });

  test('retries after a service error and replaces it with session content', async () => {
    const activeResult = await new MockAttendanceService()
      .getAttendanceSession('attendance-session-active');
    let requestCount = 0;
    const retryingService: AttendanceService = {
      getAttendanceSession: async () => {
        requestCount += 1;

        if (requestCount === 1) {
          throw new Error('Simulated service failure');
        }

        return activeResult;
      },
    };
    const {
      findByRole,
      findByText,
      getByRole,
    } = await renderScreen(createScreenProps(retryingService));

    await findByText("We couldn't load this session");
    expect(
      getByRole('button', {
        name: 'Go back',
      }),
    ).toBeTruthy();

    const retryButton = getByRole('button', {
      name: 'Retry loading attendance session',
    });

    fireEvent.press(retryButton);

    await findByText('Architecture Review Lecture');

    expect(requestCount).toBe(2);
    expect(
      await findByRole('button', {
        name: 'Start attendance check-in',
      }),
    ).toBeTruthy();
  });

  test('uses the Location, Face, Complete workflow without mandatory QR', async () => {
    const {
      findByLabelText,
      getByText,
      queryByText,
    } = await renderScreen(createScreenProps(new MockAttendanceService()));

    await findByLabelText(
      'Attendance check-in progress: Location, Face, Complete',
    );

    expect(getByText('Location')).toBeTruthy();
    expect(getByText('Face')).toBeTruthy();
    expect(getByText('Complete')).toBeTruthy();
    expect(queryByText(/Identity|Classroom/)).toBeNull();
    expect(queryByText(/QR|Waiting for QR/i)).toBeNull();
  });
});
