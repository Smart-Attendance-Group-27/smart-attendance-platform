export type LineChartPoint = {
  label: string;
  value: number;
};

type LineChartProps = {
  data: LineChartPoint[];
  minValue?: number;
  maxValue?: number;
  ariaLabel: string;
};

const VIEW_WIDTH = 720;
const VIEW_HEIGHT = 240;
const PLOT_LEFT = 50;
const PLOT_RIGHT = 700;
const PLOT_TOP = 30;
const PLOT_BOTTOM = 190;

export function LineChart({ data, minValue, maxValue, ariaLabel }: LineChartProps) {
  if (data.length === 0) return null;

  const values = data.map((point) => point.value);
  const max = maxValue ?? Math.max(...values);
  const min = minValue ?? Math.min(...values, 0);
  const range = max - min || 1;

  const step = data.length > 1 ? (PLOT_RIGHT - PLOT_LEFT) / (data.length - 1) : 0;

  const points = data.map((point, index) => {
    const x = PLOT_LEFT + step * index;
    const y = PLOT_BOTTOM - ((point.value - min) / range) * (PLOT_BOTTOM - PLOT_TOP);
    return { x, y, label: point.label, value: point.value };
  });

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${PLOT_BOTTOM} L ${points[0].x} ${PLOT_BOTTOM} Z`;

  const gridLines = [0.25, 0.5, 0.75, 1].map((fraction) => PLOT_TOP + fraction * (PLOT_BOTTOM - PLOT_TOP));

  return (
    <svg viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`} role="img" aria-label={ariaLabel} className="w-full">
      {gridLines.map((y) => (
        <line key={y} x1={PLOT_LEFT} y1={y} x2={PLOT_RIGHT} y2={y} stroke="#e1e5e9" strokeWidth={1} />
      ))}
      <path d={areaPath} fill="#dcebf5" opacity={0.7} />
      <path d={linePath} fill="none" stroke="var(--uom-blue)" strokeWidth={3} />
      {points.map((point) => (
        <circle key={point.label} cx={point.x} cy={point.y} r={4} fill="#fff" stroke="var(--uom-blue)" strokeWidth={2} />
      ))}
      {points.map((point) => (
        <text
          key={`${point.label}-label`}
          x={point.x}
          y={PLOT_BOTTOM + 24}
          textAnchor="middle"
          fontSize={10}
          fill="#687581"
        >
          {point.label}
        </text>
      ))}
    </svg>
  );
}
