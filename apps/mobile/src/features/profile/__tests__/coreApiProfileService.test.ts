import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiProfileService } from '../services/coreApiProfileService';
import { CoreApiClient } from '../../../services/api/coreApiClient';

const accessToken = 'header.payload.signature';

const backendProfile = {
  id: '23000000-0000-0000-0000-000000000001',
  registrationNumber: '230701A',
  fullName: 'Amal Perera',
  universityEmail: '230701a@student.uniattend.test',
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildServiceWithToken(token: string | undefined) {
  return new CoreApiProfileService(
    new CoreApiClient({
      baseUrl: 'http://10.0.2.2:8000',
      getAccessToken: () => token,
    }),
  );
}

function buildService() {
  return buildServiceWithToken(accessToken);
}

describe('CoreApiProfileService', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('requests the student profile endpoint with a bearer token', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, backendProfile));

    await buildService().getMyStudentProfile();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/students/me/profile',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: `Bearer ${accessToken}`,
        }),
      }),
    );
  });

  test('sends no student identifier of its own', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, backendProfile));

    await buildService().getMyStudentProfile();

    const [requestedUrl] = fetchMock.mock.calls[0] as [string];
    expect(requestedUrl).not.toContain('?');
    expect(requestedUrl).toMatch(/\/students\/me\/profile$/);
  });

  test('maps a successful response to a student profile', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, backendProfile));

    await expect(buildService().getMyStudentProfile()).resolves.toEqual({
      status: 'found',
      profile: backendProfile,
    });
  });

  test('maps 401 to an unauthenticated result', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(401, { detail: 'token expired' }));

    await expect(buildService().getMyStudentProfile()).resolves.toEqual({
      status: 'unauthenticated',
    });
  });

  test('maps 403 to a forbidden result', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(403, { detail: 'student role required' }));

    await expect(buildService().getMyStudentProfile()).resolves.toEqual({
      status: 'forbidden',
    });
  });

  test('maps 404 to a missing profile', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(404, { detail: 'not found' }));

    await expect(buildService().getMyStudentProfile()).resolves.toEqual({
      status: 'missing',
    });
  });

  test('maps a server error to a failure', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(jsonResponse(500, {}));

    await expect(buildService().getMyStudentProfile()).resolves.toEqual({
      status: 'failed',
    });
  });

  test('maps a network failure to a failure, never to mock data', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockRejectedValue(new Error('Network request failed'));

    const result = await buildService().getMyStudentProfile();

    expect(result).toEqual({ status: 'failed' });
    expect(result).not.toHaveProperty('profile');
  });

  test('rejects a response that is missing required fields', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, { id: 'profile-1' }));

    await expect(buildService().getMyStudentProfile()).resolves.toEqual({
      status: 'failed',
    });
  });

  test('reports an unauthenticated result when there is no token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');

    await expect(
      buildServiceWithToken(undefined).getMyStudentProfile(),
    ).resolves.toEqual({
      status: 'unauthenticated',
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
