// @vitest-environment node
//
// session.ts is genuinely server-only code, so testing it needs no DOM.
import { describe, expect, it, vi } from "vitest";
import type { SessionPayload } from "@/lib/auth/session";

// `server-only` resolves to a no-op file only when a bundler applies Next.js's
// "react-server" export condition (see node_modules/server-only/package.json) —
// Vitest doesn't know about that condition, so the package's default export
// (which unconditionally throws) is what loads. Mock it away for the test.
vi.mock("server-only", () => ({}));

const { decryptSession, encryptSession } = await import("@/lib/auth/session");

const SAMPLE_PAYLOAD: SessionPayload = {
  userId: "11111111-1111-1111-1111-111111111111",
  name: "Prof. Dulani Meedeniya",
  role: "lecturer",
  refreshToken: "sample-refresh-token",
  expiresAt: new Date(Date.now() + 60_000).toISOString(),
};

describe("encryptSession / decryptSession", () => {
  it("round-trips a payload through sign and verify", async () => {
    const token = await encryptSession(SAMPLE_PAYLOAD);
    const decoded = await decryptSession(token);

    expect(decoded?.userId).toBe(SAMPLE_PAYLOAD.userId);
    expect(decoded?.name).toBe(SAMPLE_PAYLOAD.name);
    expect(decoded?.role).toBe(SAMPLE_PAYLOAD.role);
  });

  it("returns null for a missing token", async () => {
    expect(await decryptSession(undefined)).toBeNull();
  });

  it("returns null for a tampered/invalid token", async () => {
    const token = await encryptSession(SAMPLE_PAYLOAD);
    expect(await decryptSession(`${token}tampered`)).toBeNull();
  });

  it("returns null for an expired token", async () => {
    const expired = await encryptSession({ ...SAMPLE_PAYLOAD, expiresAt: new Date(Date.now() - 1000).toISOString() });
    expect(await decryptSession(expired)).toBeNull();
  });

  it("stays well under the ~4096-byte browser cookie limit with realistic Keycloak token sizes", async () => {
    // Regression test: an earlier version of this cookie stored access+refresh+ID
    // tokens together and measured ~4931 bytes against a real local Keycloak —
    // over the limit, so the browser silently dropped the cookie and every login
    // appeared to redirect to the dashboard but left the user signed out. Only the
    // refresh token is persisted now; this pins that this stays safely under the
    // limit even with a realistic (not minimal) refresh token size.
    const realisticRefreshToken = "x".repeat(750); // observed real Keycloak refresh_token: 726 chars
    const token = await encryptSession({ ...SAMPLE_PAYLOAD, refreshToken: realisticRefreshToken });
    expect(token.length).toBeLessThan(2048);
  });
});
