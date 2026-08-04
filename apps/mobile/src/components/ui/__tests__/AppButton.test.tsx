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

import { AppButton } from '../AppButton';

describe('AppButton', () => {
  test('renders its title and handles a press', async () => {
    const handlePress = jest.fn();

    const { getByRole } = await render(
      <AppButton
        title="Continue"
        onPress={handlePress}
      />,
    );

    const button = getByRole('button', {
      name: 'Continue',
    });

    await fireEvent.press(button);

    expect(handlePress).toHaveBeenCalledTimes(1);
  });

  test('does not handle a press when disabled', async () => {
    const handlePress = jest.fn();

    const { getByRole } = await render(
      <AppButton
        title="Continue"
        disabled
        onPress={handlePress}
      />,
    );

    const button = getByRole('button', {
      name: 'Continue',
    });

    await fireEvent.press(button);

    expect(handlePress).not.toHaveBeenCalled();
  });
});