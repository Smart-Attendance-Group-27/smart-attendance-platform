export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info" | "purple";

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "border-[#cfd5da] bg-[#f4f5f6] text-[#52606b] before:bg-[#88939c]",
  success: "border-[#bfdbbf] bg-[var(--success-bg)] text-[var(--success)] before:bg-[var(--success)]",
  warning: "border-[#e6cf9e] bg-[var(--warning-bg)] text-[var(--warning)] before:bg-[#c97b00]",
  danger: "border-[#e5bcbc] bg-[var(--danger-bg)] text-[var(--danger)] before:bg-[var(--danger)]",
  info: "border-[#bed3e4] bg-[var(--uom-blue-soft)] text-[var(--uom-blue)] before:bg-[var(--uom-blue)]",
  purple: "border-[#d5ccef] bg-[var(--purple-bg)] text-[var(--purple)] before:bg-[var(--purple)]",
};

type StatusBadgeProps = {
  tone?: StatusTone;
  children: React.ReactNode;
};

export function StatusBadge({ tone = "neutral", children }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex min-h-[22px] items-center gap-1.5 whitespace-nowrap border px-1.5 text-[10px] before:h-1.5 before:w-1.5 before:rounded-full before:content-[''] ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}
