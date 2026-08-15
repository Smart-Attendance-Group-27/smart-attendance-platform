import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from '@jest/globals';

import { CoreApiClient, resolveCoreApiBaseUrl } from '../coreApiClient';

const accessToken = 'header.payload.signature';

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
