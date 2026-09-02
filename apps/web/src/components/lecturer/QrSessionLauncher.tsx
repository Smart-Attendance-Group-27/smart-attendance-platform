"use client";

import { useEffect, useMemo, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField, fieldInputClassName } from "@/components/ui/FormField";
import { Notice } from "@/components/ui/Notice";
import { StatusBadge } from "@/components/ui/StatusBadge";

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

type QrSessionLauncherProps = {
  sessionId: string;
  courseCode: string;
  courseName: string;
  room: string;
  checkInWindow: string;
  isLaunchEnabled: boolean;
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds % 3600 === 0) return `${seconds / 3600}h`;
  if (seconds % 60 === 0) return `${seconds / 60}m`;
  return `${seconds}s`;
}

export function QrSessionLauncher({
  sessionId,
  courseCode,
  courseName,
  room,
  checkInWindow,
  isLaunchEnabled,
}: QrSessionLauncherProps) {
  const [mode, setMode] = useState<QrMode>("static");
  const [validForSeconds, setValidForSeconds] = useState("300");
  const [refreshIntervalSeconds, setRefreshIntervalSeconds] = useState("15");
  const [qrSession, setQrSession] = useState<QrSessionResponse | null>(null);
  const [dynamicQr, setDynamicQr] = useState<DynamicQrStreamPayload | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("idle");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const validityNumber = Number(validForSeconds);
  const refreshIntervalNumber = Number(refreshIntervalSeconds);
  const canSubmit =
    isLaunchEnabled &&
    Number.isInteger(validityNumber) &&
    validityNumber >= 30 &&
    validityNumber <= 86400 &&
    (mode === "static" ||
      (Number.isInteger(refreshIntervalNumber) &&
        refreshIntervalNumber >= 1 &&
        refreshIntervalNumber <= 300));

  const displayedQrValue =
    qrSession?.mode === "dynamic" ? dynamicQr?.qrValue : qrSession?.qrValue;

  const displayedValidFrom =
    qrSession?.mode === "dynamic" ? dynamicQr?.validFrom : qrSession?.validFrom;

  const displayedExpiresAt =
    qrSession?.mode === "dynamic" ? dynamicQr?.expiresAt : qrSession?.expiresAt;

  const qrCodePayload = useMemo(() => {
    if (!qrSession || !displayedQrValue) return "";

    return JSON.stringify({
      qrSessionId: qrSession.qrSessionId,
      qrValue: displayedQrValue,
    });
  }, [displayedQrValue, qrSession]);

  useEffect(() => {
    if (!qrSession || qrSession.mode !== "dynamic") return;

    const source = new EventSource(`/api/qr-sessions/${qrSession.qrSessionId}/stream`);

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

  async function launchQrSession() {
    if (!canSubmit) return;

    setIsLoading(true);
    setError("");
    setQrSession(null);
    setDynamicQr(null);
    setStreamStatus("idle");

    try {
      const response = await fetch(`/api/attendance-sessions/${sessionId}/qr-sessions`, {
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
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "QR session could not be launched.");
      }

      const createdSession = data as QrSessionResponse;
      if (createdSession.mode === "static" && !createdSession.qrValue) {
        throw new Error("The backend did not return a static QR value.");
      }

      setQrSession(createdSession);
      setStreamStatus(createdSession.mode === "dynamic" ? "connecting" : "idle");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unexpected QR launch error.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
      <Card title="QR launch settings" subtitle={`${courseCode} · ${room}`}>
        <div className="space-y-4">
          <Notice title="Screen sharing mode">
            Launch the QR session, then share this page with students. Static QR keeps the same value until the QR session expires; dynamic QR rotates through the live stream.
          </Notice>

          {!isLaunchEnabled ? (
            <Notice variant="warning" title="QR launch unavailable">
              This session is not currently active or QR verification is disabled.
            </Notice>
          ) : null}

          <fieldset>
            <legend className="mb-2 text-[11px] font-semibold">QR mode</legend>
            <div className="grid grid-cols-2 gap-2">
              {(["static", "dynamic"] as const).map((option) => (
                <label
                  key={option}
                  className={`cursor-pointer border px-3 py-2 text-xs ${
                    mode === option
                      ? "border-[var(--uom-blue)] bg-[var(--uom-blue-soft)] text-[var(--uom-blue)]"
                      : "border-[var(--line)] bg-white text-[#455662]"
                  }`}
                >
                  <input
                    checked={mode === option}
                    className="sr-only"
                    name="qrMode"
                    onChange={() => selectMode(option)}
                    type="radio"
                    value={option}
                  />
                  <span className="block font-semibold capitalize">{option}</span>
                  <span className="mt-1 block text-[10px] text-[var(--muted)]">
                    {option === "static" ? "One QR value" : "Auto-rotating QR"}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <FormField
            htmlFor="validForSeconds"
            label="QR session duration"
            help="Backend accepts 30 to 86,400 seconds. Expiry is also capped by the attendance session end time."
          >
            <input
              className={fieldInputClassName()}
              id="validForSeconds"
              inputMode="numeric"
              max={86400}
              min={30}
              onChange={(event) => setValidForSeconds(event.target.value)}
              type="number"
              value={validForSeconds}
            />
          </FormField>

          {mode === "dynamic" ? (
            <FormField
              htmlFor="refreshIntervalSeconds"
              label="Dynamic refresh interval"
              help="How often the displayed QR should rotate. Backend accepts 1 to 300 seconds."
            >
              <input
                className={fieldInputClassName()}
                id="refreshIntervalSeconds"
                inputMode="numeric"
                max={300}
                min={1}
                onChange={(event) => setRefreshIntervalSeconds(event.target.value)}
                type="number"
                value={refreshIntervalSeconds}
              />
            </FormField>
          ) : null}

          <Button
            className="w-full justify-center"
            disabled={!canSubmit || isLoading}
            onClick={launchQrSession}
            variant="primary"
          >
            {isLoading ? `Launching ${mode} QR session...` : `Launch ${mode} QR session`}
          </Button>

          {error ? (
            <p className="border border-[#e5bcbc] bg-[var(--danger-bg)] px-3 py-2 text-xs text-[var(--danger)]">
              {error}
            </p>
          ) : null}
        </div>
      </Card>

      <Card title="Student display" subtitle={courseName}>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
          <div className="flex min-h-[520px] items-center justify-center border border-dashed border-[#cbd4dc] bg-[#f7fafc] p-6">
            {qrSession && qrCodePayload ? (
              <div className="flex flex-col items-center text-center">
                <QRCodeSVG value={qrCodePayload} size={340} level="M" marginSize={4} />
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <StatusBadge tone={qrSession.mode === "dynamic" ? "warning" : "success"}>
                    {qrSession.mode === "dynamic" ? `Dynamic · ${streamStatus}` : "Static · active"}
                  </StatusBadge>
                  <StatusBadge tone="info">{formatDuration(validityNumber)}</StatusBadge>
                </div>
                <p className="mt-4 text-sm font-semibold text-[#2d3d49]">
                  Scan this QR after location and face verification
                </p>
                <p className="mt-1 max-w-lg text-xs leading-relaxed text-[var(--muted)]">
                  The code contains only the QR session ID and the current QR value. Raw QR values are verified by the backend and are not shown to students here.
                </p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-base font-semibold text-[#33434f]">No QR session launched</p>
                <p className="mt-2 max-w-md text-xs leading-relaxed text-[var(--muted)]">
                  Choose static or dynamic mode, set the timing, then launch the QR session for this active attendance session.
                </p>
              </div>
            )}
          </div>

          <aside className="space-y-3 text-xs">
            <div className="border border-[var(--line)] bg-[#fafbfc] p-3">
              <p className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Session</p>
              <p className="mt-1 font-semibold text-[#2d3d49]">{courseCode}</p>
              <p className="mt-1 text-[var(--muted)]">{courseName}</p>
            </div>
            <div className="border border-[var(--line)] bg-[#fafbfc] p-3">
              <p className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Check-in window</p>
              <p className="mt-1 font-semibold text-[#2d3d49]">{checkInWindow}</p>
            </div>
            <div className="border border-[var(--line)] bg-[#fafbfc] p-3">
              <p className="text-[10px] uppercase tracking-wide text-[var(--muted)]">QR session ID</p>
              <p className="mt-1 break-all font-mono text-[11px] text-[#2d3d49]">
                {qrSession?.qrSessionId ?? "—"}
              </p>
            </div>
            <div className="border border-[var(--line)] bg-[#fafbfc] p-3">
              <p className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Current value window</p>
              <dl className="mt-1 space-y-1">
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Valid from</dt>
                  <dd className="text-right font-semibold">{formatDateTime(displayedValidFrom)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--muted)]">Expires</dt>
                  <dd className="text-right font-semibold">{formatDateTime(displayedExpiresAt)}</dd>
                </div>
                {dynamicQr ? (
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--muted)]">Sequence</dt>
                    <dd className="font-semibold">{dynamicQr.sequence}</dd>
                  </div>
                ) : null}
              </dl>
            </div>
          </aside>
        </div>
      </Card>
    </div>
  );
}
