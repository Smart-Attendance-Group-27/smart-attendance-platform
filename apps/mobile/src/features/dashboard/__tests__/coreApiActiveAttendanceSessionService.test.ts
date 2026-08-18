import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiActiveAttendanceSessionService } from '../services/coreApiActiveAttendanceSessionService';

const accessToken = 'header.payload.signature';
const backendSession = {
  id: '40000000-0000-0000-0000-000000000001',
  courseCode: 'CS3203',
  courseName: 'Software Engineering Project',
  sessionTitle: 'Geofence Demo - Near Centre',
  sessionType: 'lecture',
  scheduledStartAt: '2026-08-13T05:25:00Z',
  scheduledEndAt: '2026-08-13T06:30:00Z',
  checkInOpensAt: '2026-08-13T05:28:00Z',
  checkInClosesAt: '2026-08-13T06:00:00Z',
  checkInStatus: 'open',
  lateAfterAt: '2026-08-13T05:45:00Z',
  venue: 'LH-02',
  requiresFaceVerification: true,
  requiresGeofence: true,
  requiresQr: false,
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildServiceWithToken(token: string | undefined) {
  return new CoreApiActiveAttendanceSessionService(
    new CoreApiClient({
      baseUrl: 'http://10.0.2.2:8000',
      getAccessToken: () => token,
    }),
  );
}

function buildService() {
  return buildServiceWithToken(accessToken);
}

describe('CoreApiActiveAttendanceSessionService', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('loads the signed-in student active-session endpoint', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, [backendSession]));

    await buildService().listMyActiveSessions();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/students/me/attendance-sessions/active',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: `Bearer ${accessToken}`,
        }),
      }),
    );
  });

  test('returns every validated session, including near and far demos', async () => {
    const farSession = {
      ...backendSession,
      id: '40000000-0000-0000-0000-000000000002',
      sessionTitle: 'Geofence Demo - Far Centre',
    };
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, [backendSession, farSession]));

    await expect(buildService().listMyActiveSessions()).resolves.toEqual({
      status: 'loaded',
      sessions: [backendSession, farSession],
    });
  });

  test('allows an empty active-session list', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(jsonResponse(200, []));

    await expect(buildService().listMyActiveSessions()).resolves.toEqual({
      status: 'loaded',
      sessions: [],
    });
  });

  test.each([
    [401, 'unauthenticated'],
    [403, 'forbidden'],
    [404, 'not-found'],
    [500, 'server-error'],
  ])('maps HTTP %i to %s', async (httpStatus, expectedStatus) => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(httpStatus, {}));

    await expect(buildService().listMyActiveSessions()).resolves.toEqual({
      status: expectedStatus,
    });
  });

  test('rejects malformed sessions without a mock fallback', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, [
        {
          ...backendSession,
          checkInClosesAt: 'not-a-date',
        },
      ]),
    );

    const result = await buildService().listMyActiveSessions();

    expect(result).toEqual({ status: 'server-error' });
    expect(result).not.toHaveProperty('sessions');
  });

  test('does not call the backend without an access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');

    await expect(
      buildServiceWithToken(undefined).listMyActiveSessions(),
    ).resolves.toEqual({ status: 'unauthenticated' });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
