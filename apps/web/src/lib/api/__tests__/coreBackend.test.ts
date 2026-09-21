import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { coreBackendFetch, CoreBackendError } from "@/lib/api/coreBackend";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/auth/dal", () => ({ getValidAccessToken: vi.fn().mockResolvedValue("test-token") }));

const originalBaseUrl = process.env.CORE_BACKEND_URL;
beforeEach(() => {
  process.env.CORE_BACKEND_URL = "https://backend.example.test";
});
afterEach(() => {
  process.env.CORE_BACKEND_URL = originalBaseUrl;
  vi.unstubAllGlobals();
});

describe("coreBackendFetch errors", () => {
  it("reads a structured conflict message returned by cancellation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: "SESSION_ALREADY_CLOSED", message: "A closed session cannot be cancelled." },
    }), { status: 409, headers: { "Content-Type": "application/json" } })));

    await expect(coreBackendFetch("/api/v1/lecturers/me/attendance-sessions/1/cancel", {
      method: "POST", body: { reason: "Lecturer unavailable" },
    })).rejects.toEqual(new CoreBackendError(
      "A closed session cannot be cancelled.", 409,
      "/api/v1/lecturers/me/attendance-sessions/1/cancel",
    ));
  });
});
