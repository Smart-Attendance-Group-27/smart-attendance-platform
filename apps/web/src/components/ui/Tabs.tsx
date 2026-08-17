"use client";

export type TabItem = {
  key: string;
  label: string;
  count?: number;
};

type TabsProps = {
  tabs: TabItem[];
  activeKey: string;
  onChange: (key: string) => void;
};

export function Tabs({ tabs, activeKey, onChange }: TabsProps) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1 border-b border-[var(--line)] bg-[#fafbfc] px-2 pt-2">
      {tabs.map((tab) => {
        const isActive = tab.key === activeKey;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={`rounded-t-sm border border-b-0 px-3 py-2 text-xs font-medium ${
              isActive
                ? "border-[var(--line)] bg-white text-[var(--uom-blue)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"
            }`}
          >
            {tab.label}
            {typeof tab.count === "number" ? (
              <span className="ml-1.5 text-[10px] text-[var(--muted)]">({tab.count})</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
