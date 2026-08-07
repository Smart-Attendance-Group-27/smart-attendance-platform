"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";

type QrSessionResponse = {
  qrSessionId: string;
  attendanceSessionId: string;
  qrValue: string;
  status: string;
  validFrom: string;
  expiresAt: string;
};

const DEFAULT_ATTENDANCE_SESSION_ID =
  "40000000-0000-0000-0000-000000000001";

export default function QrTestPage() {
  const [sessionId, setSessionId] = useState(DEFAULT_ATTENDANCE_SESSION_ID);
  const [validForSeconds, setValidForSeconds] = useState("300");
  const [qrSession, setQrSession] = useState<QrSessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const validityNumber = Number(validForSeconds);
  const canSubmit =
    sessionId.trim().length > 0 &&
    Number.isInteger(validityNumber) &&
    validityNumber >= 30;

  const expiryLabel = useMemo(() => {
    if (!qrSession) {
      return "";
    }

    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "medium",
    }).format(new Date(qrSession.expiresAt));
  }, [qrSession]);

  async function generateQr() {
    if (!canSubmit) {
      return;
    }

    setIsLoading(true);
    setError("");
    setQrSession(null);

    try {
      const response = await fetch(
        `/api/attendance-sessions/${sessionId.trim()}/qr-sessions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            validForSeconds: validityNumber,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "QR generation failed");
      }

      setQrSession(data as QrSessionResponse);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Unexpected error",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-100">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <Link href="/" className="w-fit text-sm text-zinc-400 hover:text-white">
          Back to home
        </Link>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <p className="text-sm font-medium uppercase tracking-wide text-cyan-300">
              QR test console
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">
              Create a static attendance QR session
            </h1>

            <div className="mt-6 space-y-5">
              <label className="block" htmlFor="sessionId">
                <span className="text-sm font-medium text-zinc-300">
                  Attendance session ID
                </span>
                <input
                  id="sessionId"
                  value={sessionId}
                  onChange={(event) => setSessionId(event.target.value)}
                  className="mt-2 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                />
              </label>

              <label className="block" htmlFor="validForSeconds">
                <span className="text-sm font-medium text-zinc-300">
                  Valid for seconds
                </span>
                <input
                  id="validForSeconds"
                  value={validForSeconds}
                  onChange={(event) => setValidForSeconds(event.target.value)}
                  inputMode="numeric"
                  className="mt-2 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                />
              </label>

              <button
                type="button"
                onClick={generateQr}
                disabled={isLoading || !canSubmit}
                className="w-full rounded-md bg-cyan-400 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
              >
                {isLoading ? "Creating QR session..." : "Create QR session"}
              </button>

              {error ? (
                <p className="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
                  {error}
                </p>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-white p-6 text-zinc-950">
            <div className="flex min-h-[520px] items-center justify-center rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-6">
              {qrSession ? (
                <div className="flex w-full flex-col items-center text-center">
                  <QRCodeSVG
                    value={qrSession.qrValue}
                    size={300}
                    level="M"
                    marginSize={4}
                  />

                  <p className="mt-5 rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-800">
                    QR session active
                  </p>
                  <p className="mt-4 max-w-xl break-all text-sm text-zinc-600">
                    {qrSession.qrSessionId}
                  </p>
                  <p className="mt-2 text-sm text-zinc-500">
                    Expires {expiryLabel}
                  </p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-lg font-medium text-zinc-700">
                    No QR generated yet
                  </p>
                  <p className="mt-2 text-sm text-zinc-500">
                    Start the FastAPI backend, then create a session from the
                    form.
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
