const defaultCoreApiBaseUrl = 'http://10.0.2.2:8000';
const defaultRequestTimeoutMs = 10_000;

/**
 * Every way a Core API call can fail, as a value rather than an exception, so
 * callers must decide what the user sees for each one.
 */
export type CoreApiFailureStatus =
  | 'unauthenticated'
  | 'forbidden'
  | 'not-found'
  | 'invalid-request'
  | 'server-error'
  | 'network-error';

export type CoreApiResult<TData> =
  | { readonly status: 'ok'; readonly data: TData }
  | { readonly status: CoreApiFailureStatus };

export type AccessTokenProvider = () =>
  | string
  | undefined
  | Promise<string | undefined>;

export type CoreApiClientOptions = {
  readonly baseUrl?: string;
  readonly getAccessToken: AccessTokenProvider;
  readonly timeoutMs?: number;
};

export function resolveCoreApiBaseUrl(): string {
  const configuredBaseUrl = process.env.EXPO_PUBLIC_CORE_API_URL?.trim();
  return stripTrailingSlash(configuredBaseUrl || defaultCoreApiBaseUrl);
}

/**
 * Shared authenticated client for the UniAttend core backend.
 *
 * The access token is read from the auth state on every call rather than held
 * here, so a refreshed or cleared session takes effect immediately. The token
 * is never logged and never stored by this client.
 */
export class CoreApiClient {
  private readonly baseUrl: string;

  private readonly getAccessToken: AccessTokenProvider;

  private readonly timeoutMs: number;

  constructor({
    baseUrl,
    getAccessToken,
    timeoutMs = defaultRequestTimeoutMs,
  }: CoreApiClientOptions) {
    this.baseUrl = baseUrl ? stripTrailingSlash(baseUrl) : resolveCoreApiBaseUrl();
    this.getAccessToken = getAccessToken;
    this.timeoutMs = timeoutMs;
  }

  async get<TData>(path: string): Promise<CoreApiResult<TData>> {
    const accessToken = await this.readAccessToken();

    if (!accessToken) {
      // No point calling the backend: it would answer 401 anyway.
      return { status: 'unauthenticated' };
    }

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      abortController.abort();
    }, this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        signal: abortController.signal,
      });

      if (!response.ok) {
        const failureStatus = mapHttpStatus(response.status);
        logCoreApiFailure(path, failureStatus, response.status);
        return { status: failureStatus };
      }

      return { status: 'ok', data: (await response.json()) as TData };
    } catch {
      // A timeout, a DNS failure, an unreachable laptop, or a body that was
      // not JSON. Never include the caught value: it can echo the request.
      logCoreApiFailure(path, 'network-error');
      return { status: 'network-error' };
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private async readAccessToken(): Promise<string | undefined> {
    try {
      const accessToken = await this.getAccessToken();
      return accessToken?.trim() ? accessToken : undefined;
    } catch {
      return undefined;
    }
  }
}

function mapHttpStatus(httpStatus: number): CoreApiFailureStatus {
  if (httpStatus === 401) {
    return 'unauthenticated';
  }

  if (httpStatus === 403) {
    return 'forbidden';
  }

  if (httpStatus === 404) {
    return 'not-found';
  }

  if (httpStatus === 400 || httpStatus === 422) {
    return 'invalid-request';
  }

  return 'server-error';
}

/**
 * Logs the request path and outcome only. The bearer token, the response body
 * and any error object are deliberately excluded.
 */
function logCoreApiFailure(
  path: string,
  failureStatus: CoreApiFailureStatus,
  httpStatus?: number,
) {
  const httpStatusSuffix = httpStatus === undefined ? '' : ` (HTTP ${httpStatus})`;
  console.warn(`Core API GET ${path} failed: ${failureStatus}${httpStatusSuffix}`);
}

function stripTrailingSlash(url: string) {
  return url.replace(/\/+$/, '');
}
