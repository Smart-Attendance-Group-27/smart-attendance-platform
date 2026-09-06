import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import FaceIntroductionRoute from '../../../app/(student)/attendance/[sessionId]/face-introduction';

const mockBack = jest.fn();
const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockRouter = {
  back: mockBack,
  push: mockPush,
  replace: mockReplace,
};
let mockSearchParams: {
  sessionId?: string | string[];
  requiresQr?: string | string[];
};

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockSearchParams,
  useRouter: () => mockRouter,
}));

jest.mock('../../auth/context/AuthContext', () => ({
  useAuth: () => ({
    session: {
      status: 'authenticated',
      accessToken: 'header.payload.signature',
    },
  }),
}));

describe('FaceIntroductionRoute', () => {
  beforeEach(() => {
    mockBack.mockClear();
    mockPush.mockClear();
    mockReplace.mockClear();
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'required' }),
    } as Response);
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('opens face verification with the normalized session ID', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const { findByRole } = await render(<FaceIntroductionRoute />);

    expect(mockPush).not.toHaveBeenCalled();

    await fireEvent.press(
      await findByRole('button', {
        name: 'Begin face verification',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith({
      pathname:
        '/(student)/attendance/[sessionId]/face-verification',
      params: {
        sessionId: 'attendance-session-active',
        requiresQr: undefined,
      },
    });
  });

  test('uses router back for the screen back action', async () => {
    const { findByRole } = await render(<FaceIntroductionRoute />);

    await fireEvent.press(
      await findByRole('button', {
        name: 'Go back',
      }),
    );

    expect(mockBack).toHaveBeenCalledTimes(1);
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('bypasses face screens when verification already passed', async () => {
    jest.mocked(global.fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'passed' }),
    } as Response);
    mockSearchParams = {
      sessionId: 'attendance-session-active',
      requiresQr: '1',
    };

    await render(<FaceIntroductionRoute />);

    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith({
        pathname: '/(student)/attendance/[sessionId]/qr-scanner',
        params: { sessionId: 'attendance-session-active' },
      }),
    );
    expect(mockPush).not.toHaveBeenCalled();
  });

  test('keeps the friendly fallback for a missing session ID', async () => {
    mockSearchParams = {};
    const { getByText, queryByRole } = await render(
      <FaceIntroductionRoute />,
    );

    expect(
      getByText(
        /We could not open this attendance step because the session link is incomplete/,
      ),
    ).toBeTruthy();
    expect(
      queryByRole('button', {
        name: 'Begin face verification',
      }),
    ).toBeNull();
    expect(mockBack).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
