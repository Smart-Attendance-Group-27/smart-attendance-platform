import { afterEach, describe, expect, jest, test } from '@jest/globals';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { myAttendanceFixtures } from '../__fixtures__/myAttendance';
import { CoreApiAttendanceService } from '../services/coreApiAttendanceService';

const baseUrl = 'http://10.0.2.2:8000';
const sessionId = 'attendance-session-checked-in';

function response(status: number, body: unknown): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

function service() {
  return new CoreApiAttendanceService(new CoreApiClient({
    baseUrl, getAccessToken: () => 'token',
  }));
}

afterEach(() => { jest.restoreAllMocks(); });

describe('CoreApiAttendanceService', () => {
  test('reads C02 initial state without calling completion', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(
      response(200, myAttendanceFixtures[sessionId]),
    );

    await expect(service().getMyAttendance(sessionId)).resolves.toEqual({
      status: 'loaded', attendance: myAttendanceFixtures[sessionId],
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/students/me/attendance-sessions/${sessionId}/attendance`,
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test('reads final attendance separately from the initial check-in', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      response(200, myAttendanceFixtures['attendance-session-closed']),
    );
    const result = await service().getMyAttendance('attendance-session-closed');
    expect(result.status).toBe('loaded');
    if (result.status === 'loaded') {
      expect(result.attendance.initialCheckIn?.status).toBe('checked_in');
      expect(result.attendance.finalAttendance?.status).toBe('present');
    }
  });

  test('maps the allocated session venue into session details', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      response(200, myAttendanceFixtures[sessionId]),
    );

    const result = await service().getAttendanceSession(sessionId);

    expect(result).toEqual(expect.objectContaining({
      status: 'available',
      session: expect.objectContaining({ venue: 'Lecture Hall 02' }),
    }));
  });

  test('reads the cancellation reason for a cancelled session', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      response(200, myAttendanceFixtures['attendance-session-cancelled']),
    );
    const result = await service().getMyAttendance('attendance-session-cancelled');
    expect(result.status).toBe('loaded');
    if (result.status === 'loaded') {
      expect(result.attendance.sessionState).toBe('cancelled');
      expect(result.attendance.cancellationReason).toBe('The lecturer is unwell.');
    }
  });

  test('rejects a payload whose cancellation reason is not a string or null', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(response(200, {
      ...myAttendanceFixtures['attendance-session-cancelled'], cancellationReason: 42,
    }));
    await expect(service().getMyAttendance('attendance-session-cancelled'))
      .resolves.toEqual({ status: 'server-error' });
  });

  test('posts C01 and parses initial check-in', async () => {
    const initialCheckIn = { status: 'late_checked_in', checkedInAt: '2026-07-20T10:18:00+05:30' };
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(response(200, {
      status: 'checked_in', verificationAttemptId: 'attempt-1',
      initialCheckIn, missingRequirements: [],
    }));
    await expect(service().checkIn(sessionId)).resolves.toEqual({
      status: 'loaded', outcome: 'checked_in', initialCheckIn, missingRequirements: [],
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/attendance-sessions/${sessionId}/check-in`,
      expect.objectContaining({ method: 'POST', body: '{}' }),
    );
  });

  test('reports incomplete C01 response without fabricating attendance', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(response(200, {
      status: 'incomplete', initialCheckIn: null,
      missingRequirements: ['face_verification'],
    }));
    await expect(service().checkIn(sessionId)).resolves.toEqual({
      status: 'loaded', outcome: 'incomplete', initialCheckIn: null,
      missingRequirements: ['face_verification'],
    });
  });

  test('rejects malformed C02 and C01 payloads', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(response(200, {
      ...myAttendanceFixtures[sessionId], initialCheckIn: { status: 'present' },
    }));
    await expect(service().getMyAttendance(sessionId)).resolves.toEqual({ status: 'server-error' });
    jest.spyOn(global, 'fetch').mockResolvedValue(response(200, {
      status: 'checked_in', initialCheckIn: { status: 'present' }, missingRequirements: [],
    }));
    await expect(service().checkIn(sessionId)).resolves.toEqual({ status: 'server-error' });
  });
  test('reads the effective policy separately from the geofence evidence', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      response(200, myAttendanceFixtures['attendance-session-geofence-waived']),
    );
    const result = await service().getMyAttendance('attendance-session-geofence-waived');
    expect(result.status).toBe('loaded');
    if (result.status === 'loaded') {
      expect(result.attendance.verificationPolicy.geofence).toBe('waived');
      expect(result.attendance.verification.geofenceStatus).toBe('failed');
    }
  });

  test('treats a missing policy from an older server as every step required', async () => {
    const { verificationPolicy: _policy, ...legacy } = myAttendanceFixtures[sessionId];
    jest.spyOn(global, 'fetch').mockResolvedValue(response(200, legacy));
    const result = await service().getMyAttendance(sessionId);
    expect(result.status === 'loaded' && result.attendance.verificationPolicy).toEqual({
      geofence: 'required', face: 'required', geofenceWaivedAt: null,
    });
  });

  test('accepts a left early final attendance', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      response(200, myAttendanceFixtures['attendance-session-left-early']),
    );
    const result = await service().getMyAttendance('attendance-session-left-early');
    expect(result.status === 'loaded' && result.attendance.finalAttendance?.status).toBe('left_early');
  });

  test('starts verification without a location reading after a waiver', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValue(response(200, {
      verificationAttemptId: 'attempt-1', geofenceRequirement: 'waived',
      nextStep: 'FACE_VERIFICATION', initialCheckIn: null,
    }));
    await expect(service().startVerificationWithoutLocation(sessionId)).resolves.toEqual({
      status: 'started', initialCheckIn: null,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/attendance-sessions/${sessionId}/verification-attempts`,
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
