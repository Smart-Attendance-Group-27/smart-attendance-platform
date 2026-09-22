import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import {
  CoreApiClient,
  resolveCoreApiBaseUrl,
  setDefaultAccessTokenRefresher,
} from '../coreApiClient';

const accessToken = 'header.payload.signature';
const refreshedAccessToken = 'refreshed.payload.signature';

function authorizationOf(call: unknown[]): string | undefined {
  const init = call[1] as { headers?: Record<string, string> } | undefined;
  return init?.headers?.Authorization;
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function buildClient(overrides: Partial<{ getAccessToken: () => string | undefined }> = {}) {
  return new CoreApiClient({
    baseUrl: 'http://10.0.2.2:8000',
    getAccessToken: overrides.getAccessToken ?? (() => accessToken),
  });
}

describe('CoreApiClient', () => {
  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
    // The refresher is module-level state; a leak would silently change how
    // every later test handles a 401.
    setDefaultAccessTokenRefresher(undefined);
  });

  test('attaches the bearer token to the request', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, { id: 'profile-1' }));
    const client = buildClient();

    const result = await client.get('/api/v1/students/me/profile');

    expect(result).toEqual({ status: 'ok', data: { id: 'profile-1' } });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/students/me/profile',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: `Bearer ${accessToken}`,
          Accept: 'application/json',
        }),
      }),
    );
  });

  test('does not call the backend when there is no access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');
    const client = buildClient({ getAccessToken: () => undefined });

    const result = await client.get('/api/v1/me');

    expect(result).toEqual({ status: 'unauthenticated' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test('treats a blank access token as no token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');
    const client = buildClient({ getAccessToken: () => '   ' });

    const result = await client.get('/api/v1/me');

    expect(result).toEqual({ status: 'unauthenticated' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test.each([
    [401, 'unauthenticated'],
    [403, 'forbidden'],
    [404, 'not-found'],
    [422, 'invalid-request'],
    [400, 'invalid-request'],
    [409, 'conflict'],
    [500, 'server-error'],
    [503, 'server-error'],
  ])('maps HTTP %i to %s', async (httpStatus, expectedStatus) => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(httpStatus, { detail: 'nope' }));
    const client = buildClient();

    const result = await client.get('/api/v1/me');

    expect(result).toEqual({ status: expectedStatus });
  });

  test('reports a network failure instead of throwing', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockRejectedValue(new Error('Network request failed'));
    const client = buildClient();

    const result = await client.get('/api/v1/me');

    expect(result).toEqual({ status: 'network-error' });
  });

  test('returns a structured backend error code without exposing its message', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse(409, {
        detail: {
          code: 'ATTENDANCE_ALREADY_COMPLETED',
          message: 'Attendance has already been recorded for this session.',
        },
      }),
    );

    await expect(buildClient().post('/api/v1/geofence-attempts', {}))
      .resolves.toEqual({
        status: 'conflict',
        errorCode: 'ATTENDANCE_ALREADY_COMPLETED',
      });
  });

  test('posts authenticated JSON without logging the request body', async () => {
    const warnMock = jest
      .spyOn(console, 'warn')
      .mockImplementation(() => undefined);
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(409, { detail: 'conflict' }));
    const client = buildClient();
    const body = { latitude: 6.795132, longitude: 79.900421 };

    const result = await client.post('/api/v1/geofence-attempts', body);

    expect(result).toEqual({ status: 'conflict' });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/geofence-attempts',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify(body),
      }),
    );
    expect(warnMock.mock.calls.flat().join(' ')).not.toContain('6.795132');
    expect(warnMock.mock.calls.flat().join(' ')).not.toContain('79.900421');
  });

  test('does not post when there is no access token', async () => {
    const fetchMock = jest.spyOn(global, 'fetch');
    const client = buildClient({ getAccessToken: () => undefined });

    const result = await client.post('/api/v1/geofence-attempts', {});

    expect(result).toEqual({ status: 'unauthenticated' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test('posts authenticated multipart data without setting its boundary', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, { status: 'passed' }));
    const client = buildClient();
    const formData = new FormData();
    formData.append('image', 'camera-image');

    await client.postFormData('/api/v1/readiness', formData);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://10.0.2.2:8000/api/v1/readiness',
      expect.objectContaining({
        method: 'POST',
        body: formData,
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
      }),
    );
  });

  test('reports a network failure when the body is not JSON', async () => {
    jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error('Unexpected token < in JSON');
      },
    } as unknown as Response);
    const client = buildClient();

    const result = await client.get('/api/v1/me');

    expect(result).toEqual({ status: 'network-error' });
  });

  test('never writes the access token to the log', async () => {
    const warnMock = jest
      .spyOn(console, 'warn')
      .mockImplementation(() => undefined);
    jest.spyOn(global, 'fetch').mockResolvedValue(jsonResponse(500, {}));
    const client = buildClient();

    await client.get('/api/v1/me');

    expect(warnMock).toHaveBeenCalled();
    const loggedText = warnMock.mock.calls.flat().join(' ');
    expect(loggedText).not.toContain(accessToken);
    expect(loggedText).not.toContain('Bearer');
  });

  test('survives an access token provider that throws', async () => {
    const client = buildClient({
      getAccessToken: () => {
        throw new Error('secure store unavailable');
      },
    });

    await expect(client.get('/api/v1/me')).resolves.toEqual({
      status: 'unauthenticated',
    });
  });

  describe('refreshing on 401', () => {
    test('refreshes and retries once with the new token', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
        .mockResolvedValueOnce(jsonResponse(200, { id: 'profile-1' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(refreshedAccessToken);

      const result = await new CoreApiClient({
        baseUrl: 'http://10.0.2.2:8000',
        getAccessToken: () => accessToken,
        refreshAccessToken,
      }).get('/api/v1/students/me/profile');

      expect(result).toEqual({ status: 'ok', data: { id: 'profile-1' } });
      expect(refreshAccessToken).toHaveBeenCalledTimes(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(authorizationOf(fetchMock.mock.calls[0])).toBe(`Bearer ${accessToken}`);
      expect(authorizationOf(fetchMock.mock.calls[1])).toBe(
        `Bearer ${refreshedAccessToken}`,
      );
    });

    test('retries at most once when the fresh token is also rejected', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValue(jsonResponse(401, { detail: 'expired' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(refreshedAccessToken);

      const result = await new CoreApiClient({
        baseUrl: 'http://10.0.2.2:8000',
        getAccessToken: () => accessToken,
        refreshAccessToken,
      }).get('/api/v1/me');

      expect(result).toEqual({ status: 'unauthenticated' });
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(refreshAccessToken).toHaveBeenCalledTimes(1);
    });

    test('does not retry when the refresh yields no token', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValue(jsonResponse(401, { detail: 'expired' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(undefined);

      const result = await new CoreApiClient({
        baseUrl: 'http://10.0.2.2:8000',
        getAccessToken: () => accessToken,
        refreshAccessToken,
      }).get('/api/v1/me');

      expect(result).toEqual({ status: 'unauthenticated' });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    test('does not retry when the refresh returns the same token', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValue(jsonResponse(401, { detail: 'expired' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(accessToken);

      const result = await new CoreApiClient({
        baseUrl: 'http://10.0.2.2:8000',
        getAccessToken: () => accessToken,
        refreshAccessToken,
      }).get('/api/v1/me');

      expect(result).toEqual({ status: 'unauthenticated' });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    test('reports the original 401 when the refresher throws', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValue(jsonResponse(401, { detail: 'expired' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockRejectedValue(new Error('keycloak unreachable'));

      const result = await new CoreApiClient({
        baseUrl: 'http://10.0.2.2:8000',
        getAccessToken: () => accessToken,
        refreshAccessToken,
      }).get('/api/v1/me');

      expect(result).toEqual({ status: 'unauthenticated' });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    test('uses the refresher registered by AuthProvider when none is passed in', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
        .mockResolvedValueOnce(jsonResponse(200, { id: 'profile-1' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(refreshedAccessToken);
      setDefaultAccessTokenRefresher(refreshAccessToken);

      const result = await buildClient().get('/api/v1/students/me/profile');

      expect(result).toEqual({ status: 'ok', data: { id: 'profile-1' } });
      expect(refreshAccessToken).toHaveBeenCalledTimes(1);
      expect(authorizationOf(fetchMock.mock.calls[1])).toBe(
        `Bearer ${refreshedAccessToken}`,
      );
    });

    test('leaves a 401 alone when no refresher is available', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValue(jsonResponse(401, { detail: 'expired' }));

      const result = await buildClient().get('/api/v1/me');

      expect(result).toEqual({ status: 'unauthenticated' });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    test('does not refresh on a non-401 failure', async () => {
      jest.spyOn(global, 'fetch').mockResolvedValue(jsonResponse(403, {}));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(refreshedAccessToken);
      setDefaultAccessTokenRefresher(refreshAccessToken);

      const result = await buildClient().get('/api/v1/me');

      expect(result).toEqual({ status: 'forbidden' });
      expect(refreshAccessToken).not.toHaveBeenCalled();
    });

    test('replays a multipart body on the retry', async () => {
      const fetchMock = jest
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
        .mockResolvedValueOnce(jsonResponse(200, { status: 'passed' }));
      const refreshAccessToken = jest
        .fn<() => Promise<string | undefined>>()
        .mockResolvedValue(refreshedAccessToken);
      setDefaultAccessTokenRefresher(refreshAccessToken);
      const formData = new FormData();
      formData.append('image', 'camera-image');

      const result = await buildClient().postFormData('/api/v1/readiness', formData);

      expect(result).toEqual({ status: 'ok', data: { status: 'passed' } });
      const retryInit = fetchMock.mock.calls[1][1] as { body?: unknown };
      expect(retryInit.body).toBe(formData);
    });

    test('never writes either token to the log while retrying', async () => {
      const warnMock = jest
        .spyOn(console, 'warn')
        .mockImplementation(() => undefined);
      jest
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
        .mockResolvedValueOnce(jsonResponse(200, {}));
      setDefaultAccessTokenRefresher(async () => refreshedAccessToken);

      await buildClient().get('/api/v1/me');

      const loggedText = warnMock.mock.calls.flat().join(' ');
      expect(loggedText).not.toContain(accessToken);
      expect(loggedText).not.toContain(refreshedAccessToken);
      expect(loggedText).not.toContain('Bearer');
    });
  });

  test('falls back to the Android emulator host when no base URL is set', () => {
    expect(resolveCoreApiBaseUrl()).toMatch(/^http:\/\//);
  });

  test('removes a trailing slash from the base URL', async () => {
    const fetchMock = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse(200, {}));
    const client = new CoreApiClient({
      baseUrl: 'http://192.168.1.5:8000/',
      getAccessToken: () => accessToken,
    });

    await client.get('/api/v1/me');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://192.168.1.5:8000/api/v1/me',
      expect.anything(),
    );
  });
});
