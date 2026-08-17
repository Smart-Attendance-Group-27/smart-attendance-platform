import { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-4 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-start">
      <div>
        <h1 className="mb-1 text-2xl font-normal leading-tight text-[#2c3b47]">{title}</h1>
        {description ? <p className="text-[13px] leading-relaxed text-[var(--muted)]">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap justify-end gap-2">{actions}</div> : null}
    </div>
  );
}
