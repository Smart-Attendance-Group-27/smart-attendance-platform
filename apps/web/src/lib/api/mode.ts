import "server-only";

export function isWebMockMode(): boolean {
  return process.env.WEB_API_MODE === "mock";
}
