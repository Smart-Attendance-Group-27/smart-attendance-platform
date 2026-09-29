import { NextResponse } from "next/server";
import { getValidAccessToken } from "@/lib/auth/dal";

const CORE_BACKEND_URL =
  process.env.CORE_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export async function POST(
  _request: Request,
  context: RouteContext<"/api/attendance-sessions/[sessionId]/qr-sessions/[qrSessionId]/deactivate">,
) {
  const { sessionId, qrSessionId } = await context.params;
  const accessToken = await getValidAccessToken();
  const backendResponse = await fetch(
    `${CORE_BACKEND_URL}/api/v1/lecturers/me/attendance-sessions/${encodeURIComponent(sessionId)}/qr-batches/${encodeURIComponent(qrSessionId)}/deactivate`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    },
  );
  const responseText = await backendResponse.text();
  return NextResponse.json(
    responseText ? JSON.parse(responseText) : null,
    { status: backendResponse.status },
  );
}
