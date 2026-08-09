import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { FaceVerificationScreen } from '../screens/FaceVerificationScreen';

describe('FaceVerificationScreen', () => {
  test('shows mock verification result and routes to QR scan action', async () => {
    const onFaceVerified = jest.fn();
    const { getByRole, getByText } = await render(
      <FaceVerificationScreen
        onFaceVerified={onFaceVerified}
        sessionId="attendance-session-active"
      />,
    );

    expect(getByRole('header', { name: 'Face verification' })).toBeTruthy();
    expect(getByText('Mock face verification passed')).toBeTruthy();

    await fireEvent.press(
      getByRole('button', {
        name: 'Continue to QR scanner',
      }),
    );

    expect(onFaceVerified).toHaveBeenCalledTimes(1);
    expect(onFaceVerified).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });
});
