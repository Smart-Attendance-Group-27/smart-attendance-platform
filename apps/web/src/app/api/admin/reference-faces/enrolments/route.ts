import { NextRequest, NextResponse } from "next/server";
import { getValidAccessToken } from "@/lib/auth/dal";

const CORE_BACKEND_URL =
  process.env.CORE_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
const MAX_UPLOAD_BYTES = 250 * 1024 * 1024;

type StreamingRequestInit = RequestInit & { duplex: "half" };

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().startsWith("multipart/form-data;")) {
    return NextResponse.json(
      { detail: "A multipart image upload is required." },
      { status: 415 },
    );
  }

  const contentLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(contentLength) && contentLength > MAX_UPLOAD_BYTES) {
    return NextResponse.json(
      { detail: "The selected image batch exceeds the 250 MB limit." },
      { status: 413 },
    );
  }
  if (!request.body) {
    return NextResponse.json({ detail: "No images were uploaded." }, { status: 400 });
  }

  const accessToken = await getValidAccessToken();
  try {
    const init: StreamingRequestInit = {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": contentType,
      },
      body: request.body,
      cache: "no-store",
      signal: request.signal,
      duplex: "half",
    };
    const backendResponse = await fetch(
      `${CORE_BACKEND_URL}/api/v1/administrators/me/reference-faces/enrolments/upload`,
      init,
    );
    const responseText = await backendResponse.text();
    const responseBody = parseJsonOrDetail(
      responseText,
      "Reference-face enrolment failed.",
    );
    return NextResponse.json(responseBody, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      { detail: "The enrolment service is unavailable." },
      { status: 502 },
    );
  }
}

function parseJsonOrDetail(responseText: string, fallbackDetail: string) {
  if (!responseText) return { detail: fallbackDetail };
  try {
    return JSON.parse(responseText);
  } catch {
    return { detail: fallbackDetail };
  }
}
