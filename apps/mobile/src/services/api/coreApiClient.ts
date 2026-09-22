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
  | 'conflict'
  | 'server-error'
  | 'network-error';

export type CoreApiResult<TData> =
  | { readonly status: 'ok'; readonly data: TData }
  | {
      readonly status: CoreApiFailureStatus;
      readonly errorCode?: string;
    };

export type AccessTokenProvider = () =>
  | string
  | undefined
  | Promise<string | undefined>;

/**
 * Renews the session and resolves to a usable access token, or to `undefined`
 * when the session could not be renewed and the user must sign in again.
 *
 * Implementations are expected to collapse concurrent calls into one round
 * trip to the identity provider - see `AuthProvider.refreshAccessToken`.
 */
export type AccessTokenRefresher = () => Promise<string | undefined>;

export type CoreApiClientOptions = {
  readonly baseUrl?: string;
  readonly getAccessToken: AccessTokenProvider;
  /**
   * Overrides the refresher registered by `AuthProvider`. Tests pass one here;
   * application code normally relies on the registered default.
   */
  readonly refreshAccessToken?: AccessTokenRefresher;
  readonly timeoutMs?: number;
};

type RequestBody =
  | { readonly kind: 'json'; readonly value: unknown }
  | { readonly kind: 'form-data'; readonly value: FormData };

type Attempt<TData> = {
  readonly httpStatus?: number;
  readonly result: CoreApiResult<TData>;
};

/**
 * The refresher every client falls back to when none was passed in.
 *
 * Screens build their own `CoreApiClient` - there are roughly eighteen call
 * sites - so threading a refresher through each one would mean every future
 * screen has to remember to. There is exactly one signed-in user, so a single
 * registered refresher matches reality: `AuthProvider` registers itself once
 * and every client, present and future, recovers from a 401 automatically.
 */
let registeredAccessTokenRefresher: AccessTokenRefresher | undefined;

export function setDefaultAccessTokenRefresher(
  refresher: AccessTokenRefresher | undefined,
) {
  registeredAccessTokenRefresher = refresher;
}

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

  private readonly refreshAccessToken?: AccessTokenRefresher;

  private readonly timeoutMs: number;

  constructor({
    baseUrl,
    getAccessToken,
    refreshAccessToken,
    timeoutMs = defaultRequestTimeoutMs,
  }: CoreApiClientOptions) {
    this.baseUrl = baseUrl ? stripTrailingSlash(baseUrl) : resolveCoreApiBaseUrl();
    this.getAccessToken = getAccessToken;
    this.refreshAccessToken = refreshAccessToken;
    this.timeoutMs = timeoutMs;
  }

  async get<TData>(path: string): Promise<CoreApiResult<TData>> {
    return this.request<TData>(path, 'GET');
  }

  async post<TData>(path: string, body: unknown): Promise<CoreApiResult<TData>> {
    return this.request<TData>(path, 'POST', {
      kind: 'json',
      value: body,
    });
  }

  async put<TData>(path: string, body: unknown): Promise<CoreApiResult<TData>> {
    return this.request<TData>(path, 'PUT', {
      kind: 'json',
      value: body,
    });
  }

  async postFormData<TData>(
    path: string,
    body: FormData,
  ): Promise<CoreApiResult<TData>> {
    return this.request<TData>(path, 'POST', {
      kind: 'form-data',
      value: body,
    });
  }

  /**
   * Sends the request, and on a 401 renews the session and sends it once more.
   *
   * A lecture outlives an access token: a student checks in at the start and
   * scans a QR batch twenty minutes later. Without this, the second call fails
   * and nothing recovers it until the app is restarted. The retry is deliberately
   * capped at one - if a freshly minted token is also rejected, the answer really
   * is "unauthenticated" and retrying again would only loop.
   */
  private async request<TData>(
    path: string,
    method: 'GET' | 'POST' | 'PUT',
    body?: RequestBody,
  ): Promise<CoreApiResult<TData>> {
    const accessToken = await this.readAccessToken();

    if (!accessToken) {
      // No point calling the backend: it would answer 401 anyway.
      return { status: 'unauthenticated' };
    }

    const attempt = await this.send<TData>(path, method, accessToken, body);

    if (attempt.httpStatus !== 401) {
      return attempt.result;
    }

    const refresher = this.refreshAccessToken ?? registeredAccessTokenRefresher;

    if (!refresher) {
      return attempt.result;
    }

    const refreshedToken = await this.runRefresh(refresher);

    // No new token means the session is genuinely over, and an unchanged one
    // would just earn the same 401.
    if (!refreshedToken || refreshedToken === accessToken) {
      return attempt.result;
    }

    const retried = await this.send<TData>(path, method, refreshedToken, body);
    return retried.result;
  }

  private async runRefresh(
    refresher: AccessTokenRefresher,
  ): Promise<string | undefined> {
    try {
      const refreshedToken = await refresher();
      return refreshedToken?.trim() ? refreshedToken : undefined;
    } catch {
      // A failed refresh is not a different outcome for the caller: the
      // original 401 already says what happened.
      return undefined;
    }
  }

  private async send<TData>(
    path: string,
    method: 'GET' | 'POST' | 'PUT',
    accessToken: string,
    body?: RequestBody,
  ): Promise<Attempt<TData>> {
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      abortController.abort();
    }, this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
          ...(body?.kind === 'json'
            ? { 'Content-Type': 'application/json' }
            : {}),
        },
        ...(body
          ? {
              body:
                body.kind === 'json'
                  ? JSON.stringify(body.value)
                  : body.value,
            }
          : {}),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const failureStatus = mapHttpStatus(response.status);
        logCoreApiFailure(method, path, failureStatus, response.status);
        const errorCode = await readErrorCode(response);
        return {
          httpStatus: response.status,
          result: errorCode
            ? { status: failureStatus, errorCode }
            : { status: failureStatus },
        };
      }

      return {
        httpStatus: response.status,
        result: { status: 'ok', data: (await response.json()) as TData },
      };
    } catch {
      // A timeout, a DNS failure, an unreachable laptop, or a body that was
      // not JSON. Never include the caught value: it can echo the request.
      logCoreApiFailure(method, path, 'network-error');
      return { result: { status: 'network-error' } };
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

async function readErrorCode(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.json()) as {
      readonly detail?: unknown;
    };
    if (!body.detail || typeof body.detail !== 'object') {
      return undefined;
    }

    const code = (body.detail as { readonly code?: unknown }).code;
    return typeof code === 'string' && code.trim() ? code : undefined;
  } catch {
    return undefined;
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

  if (httpStatus === 409) {
    return 'conflict';
  }

  return 'server-error';
}

/**
 * Logs the request path and outcome only. The bearer token, the response body
 * and any error object are deliberately excluded.
 */
function logCoreApiFailure(
  method: 'GET' | 'POST' | 'PUT',
  path: string,
  failureStatus: CoreApiFailureStatus,
  httpStatus?: number,
) {
  const httpStatusSuffix = httpStatus === undefined ? '' : ` (HTTP ${httpStatus})`;
  console.warn(`Core API ${method} ${path} failed: ${failureStatus}${httpStatusSuffix}`);
}

function stripTrailingSlash(url: string) {
  return url.replace(/\/+$/, '');
}
