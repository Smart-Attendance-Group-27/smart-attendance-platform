"use client";

import { usePathname } from "next/navigation";
import { pageTitleForPath } from "@/lib/navigation";
import { WebRole } from "@/lib/auth/roles";

type ContextBarProps = {
  role: WebRole;
};

export function ContextBar({ role }: ContextBarProps) {
  const pathname = usePathname();
  const title = pageTitleForPath(role, pathname);

  return (
    <div className="sticky top-[var(--topbar)] z-20 flex h-12 items-center gap-2.5 border-b border-[var(--line)] bg-[var(--surface)] px-4 shadow-[var(--shadow)] lg:px-7">
      <p className="truncate text-xs text-[var(--muted)]">
        <span>UniAttend</span> / <strong className="text-[var(--text)] font-semibold">{title}</strong>
      </p>
    </div>
  );
}
