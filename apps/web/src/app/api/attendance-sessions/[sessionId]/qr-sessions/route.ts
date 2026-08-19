import { NextRequest, NextResponse } from "next/server";
import { getValidAccessToken } from "@/lib/auth/dal";

const CORE_BACKEND_URL =
  process.env.CORE_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

type QrSessionRequestBody = {
  mode?: "static" | "dynamic";
  validForSeconds?: number;
  refreshIntervalSeconds?: number;
};

function isQrSessionRequestBody(value: unknown): value is QrSessionRequestBody {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    (candidate.mode === undefined ||
      candidate.mode === "static" ||
      candidate.mode === "dynamic") &&
    (candidate.validForSeconds === undefined ||
      typeof candidate.validForSeconds === "number") &&
    (candidate.refreshIntervalSeconds === undefined ||
      typeof candidate.refreshIntervalSeconds === "number")
  );
}

export async function POST(
  request: NextRequest,
  context: RouteContext<"/api/attendance-sessions/[sessionId]/qr-sessions">,
) {
  const { sessionId } = await context.params;
  const requestBody = await request.json().catch(() => ({}));

  if (!isQrSessionRequestBody(requestBody)) {
    return NextResponse.json(
      { detail: "Request body contains invalid QR session fields." },
      { status: 400 },
    );
  }

  const accessToken = await getValidAccessToken();
  const backendResponse = await fetch(
    `${CORE_BACKEND_URL}/api/v1/attendance-sessions/${sessionId}/qr-sessions`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
      cache: "no-store",
    },
  );

  const responseText = await backendResponse.text();
  const responseBody = responseText ? JSON.parse(responseText) : null;

  return NextResponse.json(responseBody, { status: backendResponse.status });
}
