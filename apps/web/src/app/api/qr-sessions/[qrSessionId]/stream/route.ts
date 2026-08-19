import { NextRequest, NextResponse } from "next/server";
import { getValidAccessToken } from "@/lib/auth/dal";

const CORE_BACKEND_URL =
  process.env.CORE_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/qr-sessions/[qrSessionId]/stream">,
) {
  const { qrSessionId } = await context.params;
  const accessToken = await getValidAccessToken();
  const backendResponse = await fetch(
    `${CORE_BACKEND_URL}/api/v1/qr-sessions/${qrSessionId}/stream`,
    {
      headers: {
        Accept: "text/event-stream",
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
      signal: request.signal,
    },
  );

  if (!backendResponse.ok) {
    const responseText = await backendResponse.text();
    const responseBody = parseJsonOrDetail(
      responseText,
      "Dynamic QR stream failed.",
    );

    return NextResponse.json(responseBody, { status: backendResponse.status });
  }

  if (!backendResponse.body) {
    return NextResponse.json(
      { detail: "Dynamic QR stream did not return a response body." },
      { status: 502 },
    );
  }

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream; charset=utf-8",
      "X-Accel-Buffering": "no",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function parseJsonOrDetail(responseText: string, fallbackDetail: string) {
  if (!responseText) {
    return { detail: fallbackDetail };
  }

  try {
    return JSON.parse(responseText);
  } catch {
    return { detail: responseText };
  }
}
