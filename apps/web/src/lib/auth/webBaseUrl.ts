import "server-only";

const DEFAULT_WEB_BASE_URL = "http://localhost:3000";

export function getWebBaseUrl(requestUrl?: string): string {
  const configured = process.env.WEB_BASE_URL;
  const fallback = requestUrl ? new URL(requestUrl).origin : DEFAULT_WEB_BASE_URL;
  const baseUrl = configured ?? fallback;
  const url = new URL(baseUrl);

  if (url.hostname === "0.0.0.0") {
    url.hostname = "localhost";
  }

  return url.origin;
}

export function webUrl(path: string, requestUrl?: string): URL {
  return new URL(path, getWebBaseUrl(requestUrl));
}
