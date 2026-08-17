import { ReactNode } from "react";

type NoticeProps = {
  variant?: "info" | "warning";
  title?: string;
  children: ReactNode;
};

export function Notice({ variant = "info", title, children }: NoticeProps) {
  const isWarning = variant === "warning";
  return (
    <div
      className={`mb-4 border-l-4 p-3 text-xs leading-relaxed ${
        isWarning
          ? "border-l-[var(--warning)] border border-[#e3c985] bg-[#fff8e8] text-[#6e5016]"
          : "border-l-[var(--uom-blue)] border border-[#c6d7e5] bg-[#eef6fb] text-[#33546b]"
      }`}
    >
      {title ? <strong className="font-semibold">{title} </strong> : null}
      {children}
    </div>
  );
}
