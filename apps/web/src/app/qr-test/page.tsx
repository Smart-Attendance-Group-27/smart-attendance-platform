"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";

type QrMode = "static" | "dynamic";
type StreamStatus = "idle" | "connecting" | "connected" | "closed";

type QrSessionResponse = {
  qrSessionId: string;
  attendanceSessionId: string;
  mode: QrMode;
  qrValue: string | null;
  refreshIntervalSeconds: number | null;
  status: string;
  validFrom: string;
  expiresAt: string;
};

type DynamicQrStreamPayload = {
  qrSessionId: string;
  qrValue: string;
  sequence: number;
  validFrom: string;
  expiresAt: string;
};

const DEFAULT_ATTENDANCE_SESSION_ID = "40000000-0000-0000-0000-000000000001";

export default function QrTestPage() {
  const [sessionId, setSessionId] = useState(DEFAULT_ATTENDANCE_SESSION_ID);
  const [validForSeconds, setValidForSeconds] = useState("300");
  const [refreshIntervalSeconds, setRefreshIntervalSeconds] = useState("15");
  const [mode, setMode] = useState<QrMode>("static");
  const [qrSession, setQrSession] = useState<QrSessionResponse | null>(null);
  const [dynamicQr, setDynamicQr] = useState<DynamicQrStreamPayload | null>(
    null,
  );
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("idle");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const validityNumber = Number(validForSeconds);
  const refreshIntervalNumber = Number(refreshIntervalSeconds);
  const canSubmit =
    sessionId.trim().length > 0 &&
    Number.isInteger(validityNumber) &&
    validityNumber >= 30 &&
    validityNumber <= 86400 &&
    (mode === "static" ||
      (Number.isInteger(refreshIntervalNumber) &&
        refreshIntervalNumber >= 1 &&
        refreshIntervalNumber <= 300));

  const displayedQrValue =
    qrSession?.mode === "dynamic" ? dynamicQr?.qrValue : qrSession?.qrValue;

  const displayedExpiresAt =
    qrSession?.mode === "dynamic" ? dynamicQr?.expiresAt : qrSession?.expiresAt;

  const qrCodePayload = useMemo(() => {
    if (!qrSession || !displayedQrValue) {
      return "";
    }

    return JSON.stringify({
      qrSessionId: qrSession.qrSessionId,
      qrValue: displayedQrValue,
    });
  }, [displayedQrValue, qrSession]);

  const expiryLabel = useMemo(() => {
    if (!displayedExpiresAt) {
      return "";
    }

    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "medium",
    }).format(new Date(displayedExpiresAt));
  }, [displayedExpiresAt]);

  useEffect(() => {
    if (!qrSession || qrSession.mode !== "dynamic") {
      return;
    }

    const source = new EventSource(
      `/api/qr-sessions/${qrSession.qrSessionId}/stream`,
    );

    source.addEventListener("qr.rotate", (event) => {
      try {
        setDynamicQr(JSON.parse(event.data) as DynamicQrStreamPayload);
        setStreamStatus("connected");
        setError("");
      } catch {
        setStreamStatus("closed");
        setError("Dynamic QR stream returned invalid data.");
        source.close();
      }
    });

    source.onerror = () => {
      setStreamStatus((currentStatus) =>
        currentStatus === "connected" ? "connected" : "closed",
      );
      setError((currentError) => currentError || "Dynamic QR stream is unavailable.");
    };

    return () => {
      source.close();
    };
  }, [qrSession]);

  function selectMode(nextMode: QrMode) {
    setMode(nextMode);
    setQrSession(null);
    setDynamicQr(null);
    setStreamStatus("idle");
    setError("");
  }

  async function generateQr() {
    if (!canSubmit) {
      return;
    }

    setIsLoading(true);
    setError("");
    setQrSession(null);
    setDynamicQr(null);
    setStreamStatus("idle");

    try {
      const response = await fetch(
        `/api/attendance-sessions/${sessionId.trim()}/qr-sessions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            mode,
            validForSeconds: validityNumber,
            ...(mode === "dynamic"
              ? { refreshIntervalSeconds: refreshIntervalNumber }
              : {}),
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "QR generation failed");
      }

      const createdSession = data as QrSessionResponse;

      if (createdSession.mode === "static" && !createdSession.qrValue) {
        throw new Error("The backend did not return a static QR value.");
      }

      setStreamStatus(createdSession.mode === "dynamic" ? "connecting" : "idle");
      setQrSession(createdSession);
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
              Create an attendance QR session
            </h1>

            <div className="mt-6 space-y-5">
              <fieldset>
                <legend className="text-sm font-medium text-zinc-300">
                  QR mode
                </legend>
                <div className="mt-2 grid grid-cols-2 gap-3">
                  <label
                    className={`cursor-pointer rounded-md border p-3 transition ${
                      mode === "static"
                        ? "border-cyan-400 bg-cyan-400/10"
                        : "border-zinc-700 bg-zinc-950 hover:border-zinc-500"
                    }`}
                  >
                    <input
                      checked={mode === "static"}
                      className="sr-only"
                      name="qrMode"
                      onChange={() => selectMode("static")}
                      type="radio"
                      value="static"
                    />
                    <span className="block text-sm font-semibold text-white">
                      Static
                    </span>
                    <span className="mt-1 block text-xs text-zinc-400">
                      Single QR value
                    </span>
                  </label>

                  <label
                    className={`cursor-pointer rounded-md border p-3 transition ${
                      mode === "dynamic"
                        ? "border-amber-400 bg-amber-400/10"
                        : "border-zinc-700 bg-zinc-950 hover:border-zinc-500"
                    }`}
                  >
                    <input
                      checked={mode === "dynamic"}
                      className="sr-only"
                      name="qrMode"
                      onChange={() => selectMode("dynamic")}
                      type="radio"
                      value="dynamic"
                    />
                    <span className="block text-sm font-semibold text-white">
                      Dynamic
                    </span>
                    <span className="mt-1 block text-xs text-amber-300">
                      SSE rotation
                    </span>
                  </label>
                </div>
              </fieldset>

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
                  Session validity
                </span>
                <input
                  id="validForSeconds"
                  value={validForSeconds}
                  onChange={(event) => setValidForSeconds(event.target.value)}
                  inputMode="numeric"
                  min={30}
                  max={86400}
                  type="number"
                  className="mt-2 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
                />
                <span className="mt-1 block text-xs text-zinc-500">
                  30 to 86,400 seconds
                </span>
              </label>

              {mode === "dynamic" ? (
                <label className="block" htmlFor="refreshIntervalSeconds">
                  <span className="text-sm font-medium text-zinc-300">
                    Rotation interval
                  </span>
                  <input
                    id="refreshIntervalSeconds"
                    value={refreshIntervalSeconds}
                    onChange={(event) =>
                      setRefreshIntervalSeconds(event.target.value)
                    }
                    inputMode="numeric"
                    min={1}
                    max={300}
                    type="number"
                    className="mt-2 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white outline-none focus:border-amber-400"
                  />
                  <span className="mt-1 block text-xs text-zinc-500">
                    1 to 300 seconds
                  </span>
                </label>
              ) : null}

              <button
                type="button"
                onClick={generateQr}
                disabled={isLoading || !canSubmit}
                className={`w-full rounded-md px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400 ${
                  mode === "dynamic"
                    ? "bg-amber-400 text-zinc-950 hover:bg-amber-300"
                    : "bg-cyan-400 text-zinc-950 hover:bg-cyan-300"
                }`}
              >
                {isLoading
                  ? `Creating ${mode} QR session...`
                  : `Create ${mode} QR session`}
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
              {qrSession && qrCodePayload ? (
                <div className="flex w-full flex-col items-center text-center">
                  <QRCodeSVG
                    value={qrCodePayload}
                    size={300}
                    level="M"
                    marginSize={4}
                  />

                  <p
                    className={`mt-5 rounded-full px-3 py-1 text-sm font-medium ${
                      qrSession.mode === "dynamic"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-emerald-100 text-emerald-800"
                    }`}
                  >
                    {qrSession.mode === "dynamic"
                      ? `Dynamic QR ${streamStatus}`
                      : "Static QR active"}
                  </p>
                  <p className="mt-4 max-w-xl break-all text-sm text-zinc-600">
                    {qrSession.qrSessionId}
                  </p>
                  {dynamicQr ? (
                    <p className="mt-2 text-sm text-zinc-500">
                      Sequence {dynamicQr.sequence}
                    </p>
                  ) : null}
                  <p className="mt-2 text-sm text-zinc-500">
                    Expires {expiryLabel}
                  </p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-lg font-medium text-zinc-700">
                    {qrSession?.mode === "dynamic" && streamStatus === "connecting"
                      ? "Opening dynamic QR stream"
                      : "No QR session active"}
                  </p>
                  <p className="mt-2 text-sm text-zinc-500">
                    Start the FastAPI backend, then create a QR session.
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
