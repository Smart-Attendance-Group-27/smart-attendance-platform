"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
  activeBatchId?: string | null;
  activeBatchExpiresAt?: string | null;
  mockReadOnly?: boolean;
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
  activeBatchId = null,
  activeBatchExpiresAt = null,
  mockReadOnly = false,
}: QrSessionLauncherProps) {
  const [mode, setMode] = useState<QrMode>("static");
  const [validForSeconds, setValidForSeconds] = useState("");
  const [refreshIntervalSeconds, setRefreshIntervalSeconds] = useState("15");
  const [qrSession, setQrSession] = useState<QrSessionResponse | null>(null);
  const [dynamicQr, setDynamicQr] = useState<DynamicQrStreamPayload | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("idle");
  const [isLoading, setIsLoading] = useState(false);
  const [isDeactivating, setIsDeactivating] = useState(false);
  const [error, setError] = useState("");
  const [projectionRoot, setProjectionRoot] = useState<HTMLElement | null>(null);
  const [hasExistingActiveBatch, setHasExistingActiveBatch] = useState(
    () => Boolean(activeBatchExpiresAt && new Date(activeBatchExpiresAt).getTime() > Date.now()),
  );
  const projectionWindowRef = useRef<Window | null>(null);
  const projectionBeforeUnloadRef = useRef<((event: BeforeUnloadEvent) => void) | null>(null);

  const validityNumber = Number(validForSeconds);
  const refreshIntervalNumber = Number(refreshIntervalSeconds);
  const canSubmit =
    isLaunchEnabled &&
    !hasExistingActiveBatch &&
    !qrSession &&
    (validForSeconds === "" || (Number.isInteger(validityNumber) &&
      validityNumber >= 30 && validityNumber <= 86400)) &&
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

  useEffect(() => {
    if (!activeBatchExpiresAt) {
      const timeout = window.setTimeout(() => setHasExistingActiveBatch(false), 0);
      return () => window.clearTimeout(timeout);
    }

    const delay = Math.max(0, new Date(activeBatchExpiresAt).getTime() - Date.now());
    const syncTimeout = window.setTimeout(() => setHasExistingActiveBatch(delay > 0), 0);
    const expiryTimeout = window.setTimeout(() => setHasExistingActiveBatch(false), delay);
    return () => {
      window.clearTimeout(syncTimeout);
      window.clearTimeout(expiryTimeout);
    };
  }, [activeBatchExpiresAt]);

  useEffect(() => {
    if (!qrSession) return;

    const expiresAt = new Date(qrSession.expiresAt).getTime();
    const delay = Math.max(0, expiresAt - Date.now());
    const timeout = window.setTimeout(() => {
      const projectionWindow = projectionWindowRef.current;
      const beforeUnload = projectionBeforeUnloadRef.current;
      if (projectionWindow && beforeUnload) {
        projectionWindow.removeEventListener("beforeunload", beforeUnload);
      }
      projectionWindow?.close();
      projectionWindowRef.current = null;
      projectionBeforeUnloadRef.current = null;
      setProjectionRoot(null);
      setQrSession(null);
      window.focus();
    }, delay);

    return () => window.clearTimeout(timeout);
  }, [qrSession]);

  useEffect(() => () => {
    const projectionWindow = projectionWindowRef.current;
    const beforeUnload = projectionBeforeUnloadRef.current;
    if (projectionWindow && beforeUnload) {
      projectionWindow.removeEventListener("beforeunload", beforeUnload);
    }
    projectionWindow?.close();
  }, []);

  function openProjectionWindow(): Window | null {
    const projectionWindow = window.open(
      "",
      `attendance-qr-${sessionId}`,
      "popup=yes,width=1200,height=900",
    );

    if (!projectionWindow) return null;

    projectionWindow.document.title = `${courseCode} attendance QR`;
    projectionWindow.document.head.replaceChildren();
    projectionWindow.document.body.replaceChildren();
    projectionWindow.document.body.style.margin = "0";

    const style = projectionWindow.document.createElement("style");
    style.textContent = `
      * { box-sizing: border-box; }
      body { background: #f4f7fa; color: #172b3a; font-family: Arial, sans-serif; }
      .qr-projector { align-items: center; display: flex; justify-content: center; min-height: 100vh; padding: 40px; text-align: center; }
      .qr-projector__panel { background: white; border: 1px solid #d8e0e7; box-shadow: 0 18px 50px rgba(23, 43, 58, .12); max-width: 900px; padding: 48px; width: 100%; }
      .qr-projector__course { color: #526572; font-size: 24px; margin: 0 0 28px; }
      .qr-projector__code { display: block; height: auto; margin: 0 auto; max-height: 62vh; max-width: 100%; width: min(62vh, 620px); }
      .qr-projector__instruction { font-size: 26px; font-weight: 700; margin: 28px 0 8px; }
      .qr-projector__meta { color: #526572; font-size: 18px; margin: 0; }
      .qr-projector__loading { color: #526572; font-size: 24px; margin: 0; }
    `;
    projectionWindow.document.head.appendChild(style);

    const root = projectionWindow.document.createElement("div");
    projectionWindow.document.body.appendChild(root);
    projectionWindowRef.current = projectionWindow;
    setProjectionRoot(root);
    projectionWindow.focus();

    return projectionWindow;
  }

  function selectMode(nextMode: QrMode) {
    setMode(nextMode);
    setQrSession(null);
    setDynamicQr(null);
    setStreamStatus("idle");
    setError("");
  }

  async function launchQrSession() {
    if (!canSubmit) return;

    const projectionWindow = openProjectionWindow();
    if (!projectionWindow) {
      setError("The QR display window was blocked. Allow pop-ups for this site and try again.");
      return;
    }

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
          ...(validForSeconds === "" ? {} : { validForSeconds: validityNumber }),
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
      const preventClose = (event: BeforeUnloadEvent) => {
        if (Date.now() < new Date(createdSession.expiresAt).getTime()) {
          event.preventDefault();
          event.returnValue = "";
        }
      };
      projectionBeforeUnloadRef.current = preventClose;
      projectionWindow.addEventListener("beforeunload", preventClose);
      setStreamStatus(createdSession.mode === "dynamic" ? "connecting" : "idle");
    } catch (caughtError) {
      projectionWindow.close();
      projectionWindowRef.current = null;
      setProjectionRoot(null);
      setError(caughtError instanceof Error ? caughtError.message : "Unexpected QR launch error.");
    } finally {
      setIsLoading(false);
    }
  }

  async function deactivateQrSession() {
    const qrSessionId = qrSession?.qrSessionId ?? activeBatchId;
    if (!qrSessionId || isDeactivating) return;

    setIsDeactivating(true);
    setError("");
    try {
      const response = await fetch(
        `/api/attendance-sessions/${sessionId}/qr-sessions/${qrSessionId}/deactivate`,
        { method: "POST" },
      );
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(data?.detail?.message ?? data?.detail ?? "QR batch could not be deactivated.");
      }

      const projectionWindow = projectionWindowRef.current;
      const beforeUnload = projectionBeforeUnloadRef.current;
      if (projectionWindow && beforeUnload) {
        projectionWindow.removeEventListener("beforeunload", beforeUnload);
      }
      projectionWindow?.close();
      projectionWindowRef.current = null;
      projectionBeforeUnloadRef.current = null;
      setProjectionRoot(null);
      setQrSession(null);
      setDynamicQr(null);
      setHasExistingActiveBatch(false);
      setStreamStatus("idle");
      window.focus();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unexpected QR deactivation error.");
    } finally {
      setIsDeactivating(false);
    }
  }

  const projection = projectionRoot
    ? createPortal(
        <main className="qr-projector">
          <section className="qr-projector__panel">
            {qrSession && qrCodePayload ? (
              <>
                <p className="qr-projector__course">{courseCode} · {courseName} · {room}</p>
                <QRCodeSVG
                  className="qr-projector__code"
                  value={qrCodePayload}
                  size={620}
                  level="M"
                  marginSize={4}
                />
                <p className="qr-projector__instruction">Scan QR to complete check-in</p>
                <p className="qr-projector__meta">
                  Scan before {formatDateTime(qrSession.expiresAt)}
                </p>
              </>
            ) : (
              <p className="qr-projector__loading">Preparing attendance QR…</p>
            )}
          </section>
        </main>,
        projectionRoot,
      )
    : null;

  return (
    <>
      {projection}
      <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
        <Card className="h-full" title="QR launch settings" subtitle={`${courseCode} · ${room}`}>
        <div className="space-y-4">
          {!isLaunchEnabled ? (
            <Notice variant="warning" title="QR launch unavailable">
              {mockReadOnly
                ? "Mock mode shows sample QR batches. Connect the backend to launch a real batch."
                : "This session is not currently active or QR verification is disabled."}
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
            help="Leave blank to use the institution default. An explicit duration can be 30 to 86,400 seconds; expiry is capped by the attendance session end time."
          >
            <input
              className={fieldInputClassName()}
              id="validForSeconds"
              inputMode="numeric"
              max={86400}
              min={30}
              placeholder="Institution default"
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
            {isLoading ? "Launching QR..." : "Launch QR"}
          </Button>

          {(qrSession || (hasExistingActiveBatch && activeBatchId)) ? (
            <Button
              className="w-full justify-center"
              disabled={isDeactivating}
              onClick={deactivateQrSession}
              variant="danger"
            >
              {isDeactivating ? "Deactivating QR..." : "Deactivate QR"}
            </Button>
          ) : null}

          {hasExistingActiveBatch && !qrSession ? (
            <p className="text-xs text-[var(--muted)]">
              Wait for the active QR batch to finish before launching another one.
            </p>
          ) : null}

          {error ? (
            <p className="border border-[#e5bcbc] bg-[var(--danger-bg)] px-3 py-2 text-xs text-[var(--danger)]">
              {error}
            </p>
          ) : null}
          </div>
        </Card>

        <Card className="h-full" title="Student display" subtitle={courseName}>
        <div className="grid h-full gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
          <div className="flex h-full min-h-[240px] items-center justify-center border border-dashed border-[#cbd4dc] bg-[#f7fafc] p-6">
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
                  Scan QR to complete check-in
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
    </>
  );
}
