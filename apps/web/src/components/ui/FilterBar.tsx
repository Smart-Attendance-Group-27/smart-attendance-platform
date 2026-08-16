import { ReactNode } from "react";

type FilterBarProps = {
  children: ReactNode;
};

export function FilterBar({ children }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-[var(--line)] bg-[#fafbfc] p-2.5">
      {children}
    </div>
  );
}

export function SearchInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="search"
      {...props}
      className={`h-8 min-w-[220px] flex-1 border border-[#c8d0d7] bg-white px-2.5 text-[11px] text-[#33414c] ${props.className ?? ""}`}
    />
  );
}

export function FilterSelect(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`h-8 border border-[#c8d0d7] bg-white px-2.5 text-[11px] text-[#33414c] ${props.className ?? ""}`}
    />
  );
}
