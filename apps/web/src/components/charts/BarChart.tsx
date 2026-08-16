export type BarChartItem = {
  label: string;
  value: number;
};

type BarChartProps = {
  data: BarChartItem[];
  maxValue?: number;
  valueFormatter?: (value: number) => string;
};

export function BarChart({ data, maxValue, valueFormatter }: BarChartProps) {
  const max = maxValue ?? Math.max(...data.map((item) => item.value), 1);
  const format = valueFormatter ?? ((value: number) => `${value}%`);

  return (
    <div className="flex h-[220px] items-end gap-4 border-b border-[var(--line-soft)] px-4 pb-7 pt-4">
      {data.map((item) => (
        <div key={item.label} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
          <span className="text-[10px] text-[#46545f]">{format(item.value)}</span>
          <div
            className="w-3/5 min-h-[4px] bg-[var(--uom-blue)]"
            style={{ height: `${(item.value / max) * 100}%` }}
          />
          <span className="text-center text-[9px] text-[var(--muted)]">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
