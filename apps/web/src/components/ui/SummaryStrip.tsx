import { ReactNode } from "react";

export type SummaryItem = {
  label: string;
  value: ReactNode;
  note?: string;
  noteTone?: "neutral" | "good" | "warn";
};

const NOTE_TONE_CLASSES: Record<NonNullable<SummaryItem["noteTone"]>, string> = {
  neutral: "text-[var(--muted)]",
  good: "text-[var(--success)]",
  warn: "text-[var(--warning)]",
};

type SummaryStripProps = {
  items: SummaryItem[];
  "aria-label"?: string;
};

export function SummaryStrip({ items, ...rest }: SummaryStripProps) {
  return (
    <div
      className="mb-4 grid grid-cols-1 border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)] sm:grid-cols-2 lg:grid-cols-4"
      {...rest}
    >
      {items.map((item, index) => (
        <div
          key={item.label}
          className={`min-h-[86px] p-4 ${
            index !== items.length - 1 ? "border-b border-[var(--line-soft)] sm:border-b-0 sm:border-r" : ""
          }`}
        >
          <div className="mb-2 text-[11px] uppercase tracking-wide text-[var(--muted)]">{item.label}</div>
          <div className="text-2xl font-normal leading-none text-[#293946]">{item.value}</div>
          {item.note ? (
            <div className={`mt-1.5 text-[11px] ${NOTE_TONE_CLASSES[item.noteTone ?? "neutral"]}`}>{item.note}</div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
