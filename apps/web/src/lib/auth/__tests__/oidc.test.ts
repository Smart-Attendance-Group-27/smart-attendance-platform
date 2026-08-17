// @vitest-environment node
//
// oidc.ts is server-only code with no DOM dependency.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

beforeEach(() => {
  process.env.KEYCLOAK_ISSUER = "http://localhost:8080/realms/uniattend";
  process.env.KEYCLOAK_CLIENT_ID = "uniattend-web";
  process.env.KEYCLOAK_CLIENT_SECRET = "test-secret";
});

const { buildAuthorizationUrl, buildEndSessionUrl, generatePkcePair, generateRandomToken, isKeycloakConfigured } =
  await import("@/lib/auth/oidc");

const SAMPLE_DISCOVERY = {
  issuer: "http://localhost:8080/realms/uniattend",
  authorizationEndpoint: "http://localhost:8080/realms/uniattend/protocol/openid-connect/auth",
  tokenEndpoint: "http://localhost:8080/realms/uniattend/protocol/openid-connect/token",
  endSessionEndpoint: "http://localhost:8080/realms/uniattend/protocol/openid-connect/logout",
  jwksUri: "http://localhost:8080/realms/uniattend/protocol/openid-connect/certs",
};

describe("isKeycloakConfigured", () => {
  it("is true when all three env vars are set", () => {
    expect(isKeycloakConfigured()).toBe(true);
  });

  it("is false when a var is missing", () => {
    delete process.env.KEYCLOAK_CLIENT_SECRET;
    expect(isKeycloakConfigured()).toBe(false);
  });
});

describe("generatePkcePair", () => {
  it("produces a verifier and a challenge using only URL-safe base64 characters", () => {
    const { codeVerifier, codeChallenge } = generatePkcePair();
    expect(codeVerifier).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(codeChallenge).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(codeVerifier.length).toBeGreaterThanOrEqual(43);
  });

  it("generates a different pair on every call", () => {
    const a = generatePkcePair();
    const b = generatePkcePair();
    expect(a.codeVerifier).not.toBe(b.codeVerifier);
    expect(a.codeChallenge).not.toBe(b.codeChallenge);
  });

  it("derives the challenge deterministically from the verifier (S256)", async () => {
    const { createHash } = await import("node:crypto");
    const { codeVerifier, codeChallenge } = generatePkcePair();
    const expected = createHash("sha256")
      .update(codeVerifier)
      .digest("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    expect(codeChallenge).toBe(expected);
  });
});

describe("generateRandomToken", () => {
  it("generates a unique URL-safe token each call", () => {
    const a = generateRandomToken();
    const b = generateRandomToken();
    expect(a).not.toBe(b);
    expect(a).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});

describe("buildAuthorizationUrl", () => {
  it("includes every required OIDC + PKCE parameter", () => {
    const url = new URL(
      buildAuthorizationUrl({
        discovery: SAMPLE_DISCOVERY,
        redirectUri: "http://localhost:3000/api/auth/callback",
        state: "state-123",
        nonce: "nonce-456",
        codeChallenge: "challenge-789",
      }),
    );

    expect(url.origin + url.pathname).toBe(SAMPLE_DISCOVERY.authorizationEndpoint);
    expect(url.searchParams.get("client_id")).toBe("uniattend-web");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/auth/callback");
    expect(url.searchParams.get("state")).toBe("state-123");
    expect(url.searchParams.get("nonce")).toBe("nonce-456");
    expect(url.searchParams.get("code_challenge")).toBe("challenge-789");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("scope")).toContain("openid");
  });
});

describe("buildEndSessionUrl", () => {
  it("includes client_id, id_token_hint, and post_logout_redirect_uri", () => {
    const url = new URL(
      buildEndSessionUrl({
        discovery: SAMPLE_DISCOVERY,
        idTokenHint: "id-token-abc",
        postLogoutRedirectUri: "http://localhost:3000/login",
      }),
    );

    expect(url.origin + url.pathname).toBe(SAMPLE_DISCOVERY.endSessionEndpoint);
    expect(url.searchParams.get("client_id")).toBe("uniattend-web");
    expect(url.searchParams.get("id_token_hint")).toBe("id-token-abc");
    expect(url.searchParams.get("post_logout_redirect_uri")).toBe("http://localhost:3000/login");
  });
});
