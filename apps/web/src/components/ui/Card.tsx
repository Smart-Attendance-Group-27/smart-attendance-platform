import { ReactNode } from "react";

type CardProps = {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  flush?: boolean;
  className?: string;
  children: ReactNode;
};

export function Card({ title, subtitle, actions, flush = false, className = "", children }: CardProps) {
  return (
    <section className={`border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)] ${className}`}>
      {title ? (
        <div className="flex min-h-11 items-center gap-2.5 border-b border-[var(--line)] bg-[#fafbfc] px-3.5">
          <h2 className="text-sm font-semibold text-[#33434f]">{title}</h2>
          {subtitle ? <span className="text-[11px] text-[var(--muted)]">{subtitle}</span> : null}
          {actions ? <div className="ml-auto flex gap-1.5">{actions}</div> : null}
        </div>
      ) : null}
      <div className={flush ? "" : "p-3.5"}>{children}</div>
    </section>
  );
}
