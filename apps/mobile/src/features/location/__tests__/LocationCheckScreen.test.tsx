import { describe, expect, jest, test } from '@jest/globals';
import {
  act,
  fireEvent,
  render,
  waitFor,
} from '@testing-library/react-native';

import { LocationCheckScreen } from '../screens/LocationCheckScreen';
import type { LocationService } from '../services/locationService';
import type { LocationValidationResult } from '../types/locationValidation';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

type ScreenTestProps = {
  sessionId: string;
  locationService: LocationService;
  onBack: () => void;
  onLocationValidated: (sessionId: string) => void;
};

const retryableOutcomes: readonly {
  result: LocationValidationResult;
  title: string;
  message: string;
}[] = [
  {
    result: { status: 'permission_denied' },
    title: 'Location permission denied',
    message:
      'Location permission is required to continue attendance verification.',
  },
  {
    result: { status: 'services_disabled' },
    title: 'Location services are turned off',
    message:
      'Turn on Location Services for your phone, then check again.',
  },
  {
    result: { status: 'poor_accuracy' },
    title: 'Location accuracy is too low',
    message:
      'Move closer to the classroom or wait a moment for a more accurate location.',
  },
  {
    result: { status: 'retry_required' },
    title: 'A clearer location is needed',
    message:
      'Your location overlaps the classroom boundary. Wait a moment, then check again.',
  },
  {
    result: { status: 'stale_location' },
    title: 'Location information is out of date',
    message:
      'We could not use the current location reading. Check your location again.',
  },
  {
    result: { status: 'unavailable' },
    title: 'Location is unavailable',
    message:
      'We could not obtain your current location. Check your location settings and try again.',
  },
  {
    result: { status: 'invalid_request' },
    title: 'Location reading was not accepted',
    message:
      'Capture a new location reading and try the verification again.',
  },
  {
    result: { status: 'network_error' },
    title: 'Cannot reach UniAttend',
    message:
      'Check your connection to the attendance server, then try again.',
  },
  {
    result: { status: 'server_error' },
    title: 'Location verification is unavailable',
    message:
      'The attendance server could not verify your location. Try again shortly.',
  },
];

const terminalOutcomes: readonly {
  result: LocationValidationResult;
  title: string;
  message: string;
}[] = [
  {
    result: { status: 'outside_geofence' },
    title: 'Outside classroom area',
    message:
      'This location attempt is outside the approved classroom area.',
  },
  {
    result: { status: 'mock_location_detected' },
    title: 'Mock location detected',
    message:
      'Attendance verification cannot continue with a simulated location.',
  },
  {
    result: { status: 'session_unavailable' },
    title: 'Attendance session unavailable',
    message:
      'This session is closed, inactive, or no longer accepting location attempts.',
  },
  {
    result: { status: 'attempt_limit_reached' },
    title: 'Location attempt limit reached',
    message:
      'No more location attempts are available for this attendance check-in.',
  },
  {
    result: { status: 'unauthenticated' },
    title: 'Sign-in required',
    message:
      'Your sign-in session has expired. Sign in again before checking attendance.',
  },
  {
    result: { status: 'forbidden' },
    title: 'Attendance access denied',
    message:
      'You are not eligible to check in to this attendance session.',
  },
];

function createDeferred<T>(): Deferred<T> {
  let resolvePromise: ((value: T) => void) | undefined;
  let rejectPromise: ((reason?: unknown) => void) | undefined;
  const promise = new Promise<T>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });

  return {
    promise,
    resolve: (value) => {
      if (!resolvePromise) {
        throw new Error('Deferred Promise is not ready to resolve');
      }

      resolvePromise(value);
    },
    reject: (reason) => {
      if (!rejectPromise) {
        throw new Error('Deferred Promise is not ready to reject');
      }

      rejectPromise(reason);
    },
  };
}

function createScreenProps(
  locationService: LocationService,
): ScreenTestProps {
  return {
    sessionId: 'attendance-session-active',
    locationService,
    onBack: jest.fn(),
    onLocationValidated: jest.fn(),
  };
}

function createService(
  result: LocationValidationResult,
): {
  service: LocationService;
  validateLocation: jest.MockedFunction<LocationService['validateLocation']>;
} {
  const validateLocation = jest.fn<LocationService['validateLocation']>();
  validateLocation.mockResolvedValue(result);

  return {
    service: { validateLocation },
    validateLocation,
  };
}

function renderScreen(props: ScreenTestProps) {
  return render(<LocationCheckScreen {...props} />);
}

describe('LocationCheckScreen', () => {
  test('starts with permission guidance without calling the service', async () => {
    const { service, validateLocation } = createService({
      status: 'inside_geofence',
    });
    const props = createScreenProps(service);
    const { getByRole, getByText } = await renderScreen(props);

    expect(getByText('Location permission required')).toBeTruthy();
    expect(
      getByText(
        'Location access is required to confirm that you are inside the classroom.',
      ),
    ).toBeTruthy();
    expect(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    ).toBeTruthy();
    expect(validateLocation).not.toHaveBeenCalled();
    expect(props.onLocationValidated).not.toHaveBeenCalled();
  });

  test('shows a busy checking state and prevents duplicate requests', async () => {
    const deferred = createDeferred<LocationValidationResult>();
    const validateLocation = jest.fn<LocationService['validateLocation']>(
      () => deferred.promise,
    );
    const props = createScreenProps({ validateLocation });
    const { getByRole, findByText, queryByRole } = await renderScreen(props);
    const continueButton = getByRole('button', {
      name: 'Allow location access and check classroom location',
    });

    await fireEvent.press(continueButton);
    await fireEvent.press(continueButton);

    expect(await findByText('Checking location...')).toBeTruthy();
    expect(validateLocation).toHaveBeenCalledTimes(1);
    expect(validateLocation).toHaveBeenCalledWith(
      'attendance-session-active',
    );

    const checkingIndicator = getByRole('progressbar', {
      name: 'Checking classroom location',
    });

    expect(checkingIndicator.props.accessibilityState).toEqual(
      expect.objectContaining({ busy: true }),
    );
    expect(
      queryByRole('button', {
        name: 'Retry classroom location validation',
      }),
    ).toBeNull();
    expect(props.onLocationValidated).not.toHaveBeenCalled();

    await act(async () => {
      deferred.resolve({ status: 'outside_geofence' });
      await deferred.promise;
    });

    expect(await findByText('Outside classroom area')).toBeTruthy();
  });

  test('allows face verification only after an inside-geofence result', async () => {
    const { service } = createService({ status: 'inside_geofence' });
    const props = createScreenProps(service);
    const { findByRole, findByText, getByRole } = await renderScreen(props);

    await fireEvent.press(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );

    expect(await findByText('Inside classroom area')).toBeTruthy();
    expect(
      await findByText('Your classroom location has been verified.'),
    ).toBeTruthy();

    await fireEvent.press(
      await findByRole('button', {
        name: 'Continue to face verification',
      }),
    );

    expect(props.onLocationValidated).toHaveBeenCalledWith(
      'attendance-session-active',
    );
  });

  test.each(retryableOutcomes)(
    'shows $result.status guidance, supports retry, and blocks face navigation',
    async ({ result, title, message }) => {
      const { service, validateLocation } = createService(result);
      const props = createScreenProps(service);
      const {
        findByRole,
        findByText,
        getByRole,
        queryByRole,
      } = await renderScreen(props);

      await fireEvent.press(
        getByRole('button', {
          name: 'Allow location access and check classroom location',
        }),
      );

      expect(await findByText(title)).toBeTruthy();
      expect(await findByText(message)).toBeTruthy();
      expect(
        queryByRole('button', {
          name: 'Continue to face verification',
        }),
      ).toBeNull();
      expect(props.onLocationValidated).not.toHaveBeenCalled();

      await fireEvent.press(
        await findByRole('button', {
          name: 'Retry classroom location validation',
        }),
      );

      await waitFor(() => {
        expect(validateLocation).toHaveBeenCalledTimes(2);
      });
      expect(props.onLocationValidated).not.toHaveBeenCalled();
    },
  );

  test.each(terminalOutcomes)(
    'shows terminal $result.status guidance without another submission action',
    async ({ result, title, message }) => {
      const { service, validateLocation } = createService(result);
      const props = createScreenProps(service);
      const {
        findByText,
        getByRole,
        queryByRole,
      } = await renderScreen(props);

      await fireEvent.press(
        getByRole('button', {
          name: 'Allow location access and check classroom location',
        }),
      );

      expect(await findByText(title)).toBeTruthy();
      expect(await findByText(message)).toBeTruthy();
      expect(validateLocation).toHaveBeenCalledTimes(1);
      expect(
        queryByRole('button', {
          name: 'Retry classroom location validation',
        }),
      ).toBeNull();
      expect(
        queryByRole('button', {
          name: 'Continue to face verification',
        }),
      ).toBeNull();
      expect(props.onLocationValidated).not.toHaveBeenCalled();
    },
  );

  test('replaces a failed result with success after a real retry', async () => {
    const validateLocation = jest.fn<LocationService['validateLocation']>();
    validateLocation
      .mockResolvedValueOnce({ status: 'retry_required' })
      .mockResolvedValueOnce({ status: 'inside_geofence' });
    const props = createScreenProps({ validateLocation });
    const {
      findByRole,
      findByText,
      getByRole,
      queryByText,
    } = await renderScreen(props);

    await fireEvent.press(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );
    await findByText('A clearer location is needed');

    await fireEvent.press(
      await findByRole('button', {
        name: 'Retry classroom location validation',
      }),
    );

    expect(await findByText('Inside classroom area')).toBeTruthy();
    expect(queryByText('A clearer location is needed')).toBeNull();
    expect(validateLocation).toHaveBeenCalledTimes(2);
    expect(props.onLocationValidated).not.toHaveBeenCalled();
    expect(
      await findByRole('button', {
        name: 'Continue to face verification',
      }),
    ).toBeTruthy();
  });

  test('handles a rejected request and succeeds on retry without exposing its error', async () => {
    const validateLocation = jest.fn<LocationService['validateLocation']>();
    validateLocation
      .mockRejectedValueOnce(new Error('Native provider exploded'))
      .mockResolvedValueOnce({ status: 'inside_geofence' });
    const props = createScreenProps({ validateLocation });
    const {
      findByRole,
      findByText,
      getByRole,
      queryByText,
    } = await renderScreen(props);

    await fireEvent.press(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );

    expect(await findByText("We couldn't verify your location")).toBeTruthy();
    expect(
      await findByText(
        'Check your connection and location settings, then try again.',
      ),
    ).toBeTruthy();
    expect(queryByText('Native provider exploded')).toBeNull();

    await fireEvent.press(
      await findByRole('button', {
        name: 'Retry classroom location validation',
      }),
    );

    expect(await findByText('Inside classroom area')).toBeTruthy();
    expect(validateLocation).toHaveBeenCalledTimes(2);
    expect(props.onLocationValidated).not.toHaveBeenCalled();
  });

  test('shows the correct workflow, privacy notice, and back action without QR', async () => {
    const { service } = createService({ status: 'inside_geofence' });
    const props = createScreenProps(service);
    const {
      getByLabelText,
      getByRole,
      getByText,
      queryByText,
    } = await renderScreen(props);

    expect(getByText('Verify classroom location')).toBeTruthy();
    expect(
      getByText(
        'Your location is used once to confirm that you are within the approved classroom area.',
      ),
    ).toBeTruthy();
    expect(
      getByLabelText(
        'Attendance check-in progress: Location, Face, Complete',
      ),
    ).toBeTruthy();
    expect(getByText('Location')).toBeTruthy();
    expect(getByText('Current')).toBeTruthy();
    expect(getByText('Face')).toBeTruthy();
    expect(getByText('Waiting')).toBeTruthy();
    expect(getByText('Complete')).toBeTruthy();
    expect(getByText('Pending')).toBeTruthy();
    expect(
      getByText(
        'Location is checked only while completing this attendance verification.',
      ),
    ).toBeTruthy();
    expect(queryByText('Identity')).toBeNull();
    expect(queryByText('Classroom')).toBeNull();
    expect(queryByText(/QR|Waiting for QR/i)).toBeNull();

    await fireEvent.press(
      getByRole('button', {
        name: 'Go back',
      }),
    );

    expect(props.onBack).toHaveBeenCalledTimes(1);
  });

  test('ignores an older request after the validation context changes', async () => {
    const olderRequest = createDeferred<LocationValidationResult>();
    const olderValidateLocation =
      jest.fn<LocationService['validateLocation']>(
        () => olderRequest.promise,
      );
    const newerValidateLocation =
      jest.fn<LocationService['validateLocation']>();
    newerValidateLocation.mockResolvedValue({
      status: 'inside_geofence',
    });
    const initialProps = createScreenProps({
      validateLocation: olderValidateLocation,
    });
    const { findByText, getByRole, queryByText, rerender } =
      await renderScreen(initialProps);

    await fireEvent.press(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );
    await findByText('Checking location...');

    await rerender(
      <LocationCheckScreen
        {...initialProps}
        locationService={{ validateLocation: newerValidateLocation }}
        sessionId="attendance-session-newer"
      />,
    );

    await fireEvent.press(
      await getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );
    await findByText('Inside classroom area');

    await act(async () => {
      olderRequest.resolve({ status: 'outside_geofence' });
      await olderRequest.promise;
    });

    expect(queryByText('Outside classroom area')).toBeNull();
    expect(getByRole('button', {
      name: 'Continue to face verification',
    })).toBeTruthy();
  });

  test('ignores a pending result after unmounting', async () => {
    const pendingRequest = createDeferred<LocationValidationResult>();
    const validateLocation = jest.fn<LocationService['validateLocation']>(
      () => pendingRequest.promise,
    );
    const consoleError = jest
      .spyOn(console, 'error')
      .mockImplementation(() => undefined);
    const props = createScreenProps({ validateLocation });
    const { getByRole, unmount } = await renderScreen(props);

    await fireEvent.press(
      getByRole('button', {
        name: 'Allow location access and check classroom location',
      }),
    );
    await unmount();

    await act(async () => {
      pendingRequest.resolve({ status: 'inside_geofence' });
      await pendingRequest.promise;
    });

    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
