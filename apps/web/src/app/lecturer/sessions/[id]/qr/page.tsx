import { notFound } from "next/navigation";
import { QrSessionLauncher } from "@/components/lecturer/QrSessionLauncher";
import { LinkButton } from "@/components/ui/LinkButton";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getSessionDetail } from "@/services/lecturerService";

export default async function LecturerSessionQrPage(props: PageProps<"/lecturer/sessions/[id]/qr">) {
  const { id } = await props.params;
  const session = await getSessionDetail(id);

  if (!session) {
    notFound();
  }

  const isLaunchEnabled = session.status === "in_progress" && session.requiresQr === true;

  return (
    <div>
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
        isLaunchEnabled={isLaunchEnabled}
        room={session.room}
        sessionId={session.sessionId}
      />
    </div>
  );
}
