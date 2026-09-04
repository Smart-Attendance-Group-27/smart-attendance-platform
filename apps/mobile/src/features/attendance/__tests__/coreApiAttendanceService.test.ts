import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiAttendanceService } from '../services/coreApiAttendanceService';

const accessToken = 'header.payload.signature';
const baseUrl = 'http://10.0.2.2:8000';

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildService() {
  return new CoreApiAttendanceService(
    new CoreApiClient({ baseUrl, getAccessToken: () => accessToken }),
  );
}

describe('CoreApiAttendanceService.getCheckInResult', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('reports the provisional checked-in state the backend returns', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'checked_in',
        attendanceStatus: null,
        missingRequirements: [],
        checkedInAt: '2026-08-19T12:45:34.235Z',
      }),
    );

    const lookup = await buildService().getCheckInResult('session-1');

    expect(lookup).toEqual({
      status: 'available',
      result: {
        sessionId: 'session-1',
        status: 'checked_in',
        checkInTime: '2026-08-19T12:45:34.235Z',
      },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/attendance-sessions/session-1/complete-check-in`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        }),
      }),
    );
  });

  test('never invents a final attendance status from a check-in', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'checked_in',
        attendanceStatus: null,
        missingRequirements: [],
        checkedInAt: '2026-08-19T12:45:34.235Z',
      }),
    );

    const lookup = await buildService().getCheckInResult('session-1');

    expect(lookup.status === 'available' && lookup.result.status).not.toBe('present');
    expect(lookup.status === 'available' && lookup.result.status).not.toBe('late');
  });

  test('reports the final status when the session was already finalized', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'completed',
        attendanceStatus: 'present',
        missingRequirements: [],
        checkedInAt: '2026-08-19T12:45:34.235Z',
      }),
    );

    const lookup = await buildService().getCheckInResult('session-1');

    expect(lookup.status).toBe('available');
    expect(lookup.status === 'available' && lookup.result.status).toBe('present');
  });

  test('reports late when a finalized session settled on late', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'completed',
        attendanceStatus: 'late',
        missingRequirements: [],
        checkedInAt: '2026-08-19T12:45:34.235Z',
      }),
    );

    const lookup = await buildService().getCheckInResult('session-1');

    expect(lookup.status).toBe('available');
    expect(lookup.status === 'available' && lookup.result.status).toBe('late');
  });

  test('reports unavailable when checked_in arrives without a timestamp', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'checked_in',
        attendanceStatus: null,
        missingRequirements: [],
        checkedInAt: null,
      }),
    );

    await expect(buildService().getCheckInResult('session-1')).resolves.toEqual({
      status: 'unavailable',
    });
  });

  test('reports unavailable when a required step has not passed yet', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'incomplete',
        attendanceStatus: null,
        missingRequirements: ['face_verification'],
        checkedInAt: null,
      }),
    );

    await expect(buildService().getCheckInResult('session-1')).resolves.toEqual({
      status: 'unavailable',
    });
  });

  test('reports unavailable when the verification attempt failed', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        status: 'failed',
        attendanceStatus: null,
        missingRequirements: [],
        checkedInAt: null,
      }),
    );

    await expect(buildService().getCheckInResult('session-1')).resolves.toEqual({
      status: 'unavailable',
    });
  });

  test('reports unavailable when the backend request fails outright', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(jsonResponse(409, { detail: 'not started' }));

    await expect(buildService().getCheckInResult('session-1')).resolves.toEqual({
      status: 'unavailable',
    });
  });
});
