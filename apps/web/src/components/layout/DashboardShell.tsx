import { ReactNode } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { ContextBar } from "@/components/layout/ContextBar";
import { WebRole } from "@/lib/auth/roles";

type DashboardShellProps = {
  userName: string;
  role: WebRole;
  children: ReactNode;
};

export function DashboardShell({ userName, role, children }: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-[var(--page)]">
      <TopBar userName={userName} role={role} />
      <Sidebar role={role} />
      <div className="pb-14 pt-[var(--topbar)] lg:pb-0 lg:pl-[var(--rail-w)]">
        <ContextBar role={role} />
        <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-7 sm:py-8">{children}</main>
      </div>
    </div>
  );
}
