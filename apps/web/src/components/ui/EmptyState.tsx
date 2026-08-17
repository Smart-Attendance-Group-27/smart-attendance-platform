import { ReactNode } from "react";
import { InboxIcon } from "@/components/icons";

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <InboxIcon aria-hidden="true" width={28} height={28} className="text-[var(--muted)]" />
      <p className="text-sm font-semibold text-[var(--text)]">{title}</p>
      {description ? <p className="max-w-sm text-xs text-[var(--muted)]">{description}</p> : null}
      {action}
    </div>
  );
}
