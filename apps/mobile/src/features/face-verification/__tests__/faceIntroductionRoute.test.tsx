import {
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import FaceIntroductionRoute from '../../../app/(student)/attendance/[sessionId]/face-introduction';

const mockBack = jest.fn();
const mockPush = jest.fn();
let mockSearchParams: {
  sessionId?: string | string[];
};

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => mockSearchParams,
  useRouter: () => ({
    back: mockBack,
    push: mockPush,
  }),
}));

describe('FaceIntroductionRoute', () => {
  beforeEach(() => {
    mockBack.mockClear();
    mockPush.mockClear();
    mockSearchParams = {
      sessionId: 'attendance-session-active',
    };
  });

  test('opens face verification with the normalized session ID', async () => {
    mockSearchParams = {
      sessionId: [' attendance-session-active ', 'ignored-session'],
    };
    const { getByRole } = await render(<FaceIntroductionRoute />);

    expect(mockPush).not.toHaveBeenCalled();

    await fireEvent.press(
      getByRole('button', {
        name: 'Begin face verification',
      }),
    );

    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith({
      pathname:
        '/(student)/attendance/[sessionId]/face-verification',
      params: {
        sessionId: 'attendance-session-active',
      },
    });
  });

  test('uses router back for the screen back action', async () => {
    const { getByRole } = await render(<FaceIntroductionRoute />);

    await fireEvent.press(
      getByRole('button', {
        name: 'Go back',
      }),
    );

    expect(mockBack).toHaveBeenCalledTimes(1);
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
