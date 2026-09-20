import { notFound } from "next/navigation";
import { QrSessionLauncher } from "@/components/lecturer/QrSessionLauncher";
import { LinkButton } from "@/components/ui/LinkButton";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getSessionDetail } from "@/services/lecturerService";
import { getSessionQrBatches } from "@/services/lecturerService";
import { QrBatchParticipationTable } from "@/components/lecturer/QrBatchParticipationTable";
import { SessionLiveRefresh } from "@/components/lecturer/SessionLiveRefresh";
import { isWebMockMode } from "@/lib/api/mode";

export default async function LecturerSessionQrPage(props: PageProps<"/lecturer/sessions/[id]/qr">) {
  const { id } = await props.params;
  const session = await getSessionDetail(id);

  if (!session) {
    notFound();
  }
  const batches = session.requiresQr ? await getSessionQrBatches(id) : [];

  const isLaunchEnabled = session.status === "in_progress" && session.requiresQr === true;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Launch attendance QR"
        description={`${session.courseCode} · ${session.courseName} · ${session.room}`}
        actions={
          <>
            <StatusBadge tone={isLaunchEnabled ? "success" : "neutral"}>
              {isLaunchEnabled ? "Ready to launch" : "Unavailable"}
            </StatusBadge>
            <LinkButton href={`/lecturer/sessions/${session.sessionId}`}>Back to monitor</LinkButton>
          </>
        }
      />

      <QrSessionLauncher
        checkInWindow={session.checkInWindow}
        courseCode={session.courseCode}
        courseName={session.courseName}
        isLaunchEnabled={isLaunchEnabled && !isWebMockMode()}
        mockReadOnly={isWebMockMode()}
        room={session.room}
        sessionId={session.sessionId}
      />
      {session.status === "in_progress" ? <SessionLiveRefresh /> : null}
      <QrBatchParticipationTable batches={batches} />
    </div>
  );
}
