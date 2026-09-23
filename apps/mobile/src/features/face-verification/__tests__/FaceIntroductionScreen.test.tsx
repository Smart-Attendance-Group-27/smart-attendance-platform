import { describe, expect, jest, test } from '@jest/globals';
import { fireEvent, render } from '@testing-library/react-native';

import { FaceIntroductionScreen } from '../screens/FaceIntroductionScreen';

type ScreenProps = {
  sessionId: string;
  livenessMode?: 'required' | 'off';
  onBack: () => void;
  onBeginVerification: (sessionId: string) => void;
};

function createScreenProps(): ScreenProps {
  return {
    sessionId: 'attendance-session-active',
    onBack: jest.fn(),
    onBeginVerification: jest.fn(),
  };
}

function renderScreen(props: ScreenProps) {
  return render(<FaceIntroductionScreen {...props} />);
}

describe('FaceIntroductionScreen', () => {
  test('explains the required liveness actions before identity verification', async () => {
    const props = createScreenProps();
    const { getByRole, getByText } = await renderScreen(props);

    expect(
      getByRole('header', { name: 'Face verification' }),
    ).toBeTruthy();
    expect(getByText('Get ready for face verification')).toBeTruthy();
    expect(
      getByText(
        "First, follow two camera prompts to confirm you're present. Then we'll verify your face before recording attendance.",
      ),
    ).toBeTruthy();

    expect(getByText('Use good lighting')).toBeTruthy();
    expect(
      getByText(
        'Face a light source and avoid strong backlighting or heavy shadows.',
      ),
    ).toBeTruthy();

    expect(getByText('Position your face')).toBeTruthy();
    expect(
      getByText(
        'Hold your device at eye level and keep your full face centered in the frame.',
      ),
    ).toBeTruthy();

    expect(getByText('Follow the prompts')).toBeTruthy();
    expect(
      getByText(
        'You will complete two actions: turn your head left, turn your head right, or blink by holding both eyes closed until prompted and then reopening them.',
      ),
    ).toBeTruthy();

    expect(getByText('Keep still')).toBeTruthy();
    expect(
      getByText(
        'Stay still and look directly at the camera while verification is in progress.',
      ),
    ).toBeTruthy();
  });

  test('keeps legacy mode free of liveness-required instructions', async () => {
    const props = createScreenProps();
    const { getByText, queryByText } = await renderScreen({
      ...props,
      livenessMode: 'off',
    });

    expect(
      getByText(
        "We'll use the camera to verify your face before recording attendance.",
      ),
    ).toBeTruthy();
    expect(queryByText('Follow the prompts')).toBeNull();
    expect(queryByText(/turn your head|holding both eyes/i)).toBeNull();
  });

  test('does not expose liveness implementation details', async () => {
    const props = createScreenProps();
    const { queryByText } = await renderScreen(props);

    expect(
      queryByText(/ML Kit|probabilit|yaw|JSON|HTTP 422/i),
    ).toBeNull();
  });

  test('shows Location completed, Face current, and Complete pending', async () => {
    const props = createScreenProps();
    const { getByLabelText, getByText } = await renderScreen(props);

    expect(
      getByLabelText(
        'Attendance check-in progress: Location, Face, Complete',
      ),
    ).toBeTruthy();
    expect(getByText('Location')).toBeTruthy();
    expect(getByText('Verified')).toBeTruthy();
    expect(getByText('Face')).toBeTruthy();
    expect(getByText('Current')).toBeTruthy();
    expect(getByText('Complete')).toBeTruthy();
    expect(getByText('Pending')).toBeTruthy();
  });

  test('uses explicit accessible actions and preserves the session ID', async () => {
    const props = createScreenProps();
    const { getByRole } = await renderScreen(props);
    const backButton = getByRole('button', { name: 'Go back' });
    const beginButton = getByRole('button', {
      name: 'Begin face verification',
    });

    expect(props.onBack).not.toHaveBeenCalled();
    expect(props.onBeginVerification).not.toHaveBeenCalled();

    await fireEvent.press(backButton);

    expect(props.onBack).toHaveBeenCalledTimes(1);
    expect(props.onBeginVerification).not.toHaveBeenCalled();

    await fireEvent.press(beginButton);

    expect(props.onBeginVerification).toHaveBeenCalledTimes(1);
    expect(props.onBeginVerification).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test('prevents repeated Begin Verification actions', async () => {
    const props = createScreenProps();
    const { getByRole } = await renderScreen(props);
    const beginButton = getByRole('button', {
      name: 'Begin face verification',
    });

    await fireEvent.press(beginButton);
    await fireEvent.press(beginButton);

    expect(props.onBeginVerification).toHaveBeenCalledTimes(1);
  });

  test('does not show QR, identity-first, or camera-preview UI', async () => {
    const props = createScreenProps();
    const { queryByLabelText, queryByText } = await renderScreen(props);

    expect(queryByText(/QR|Waiting for QR/i)).toBeNull();
    expect(queryByText(/^Identity$/i)).toBeNull();
    expect(queryByLabelText(/camera preview/i)).toBeNull();
  });
});
