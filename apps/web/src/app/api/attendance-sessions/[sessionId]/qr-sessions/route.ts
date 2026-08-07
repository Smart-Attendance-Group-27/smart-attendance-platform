import { NextRequest, NextResponse } from "next/server";

const CORE_BACKEND_URL =
  process.env.CORE_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

type QrSessionRequestBody = {
  validForSeconds?: number;
};

function isQrSessionRequestBody(value: unknown): value is QrSessionRequestBody {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    candidate.validForSeconds === undefined ||
    typeof candidate.validForSeconds === "number"
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
      { detail: "Request body must contain numeric validForSeconds." },
      { status: 400 },
    );
  }

  const backendResponse = await fetch(
    `${CORE_BACKEND_URL}/api/v1/attendance-sessions/${sessionId}/qr-sessions`,
    {
      method: "POST",
      headers: {
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
