import "server-only";
import { getValidAccessToken } from "@/lib/auth/dal";

export class CoreBackendError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly path: string,
  ) {
    super(message);
    this.name = "CoreBackendError";
  }
}

function getBaseUrl(): string {
  const baseUrl = process.env.CORE_BACKEND_URL;
  if (!baseUrl) {
    throw new Error("CORE_BACKEND_URL is not set.");
  }
  return baseUrl;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  body?: unknown;
  searchParams?: Record<string, string | number | undefined>;
};

// Every lecturer/administrator page reads through this — it attaches the
// caller's Keycloak access token (refreshed on demand by getValidAccessToken)
// and never caches, since attendance/review/admin data is only ever current.
export async function coreBackendFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const accessToken = await getValidAccessToken();
  const url = new URL(path, getBaseUrl());
  if (options.searchParams) {
    for (const [key, value] of Object.entries(options.searchParams)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new CoreBackendError(detail, response.status, path);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? `core-backend request failed with ${response.status}`;
  } catch {
    return `core-backend request failed with ${response.status}`;
  }
}
