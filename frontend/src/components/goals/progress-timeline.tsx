"use client";

type ProgressTimelinePoint = {
  label: string;
  value: number;
};

type ProgressTimelineProps = {
  points: ProgressTimelinePoint[];
  title?: string;
};

export function ProgressTimeline({ points, title = "Progress Timeline" }: ProgressTimelineProps) {
  if (points.length < 2) {
    return (
      <div className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-4">
        <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">{title}</p>
        <p className="mt-2 text-sm text-[var(--muted)]">Log at least two updates to see trendlines.</p>
      </div>
    );
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 620;
  const height = 180;
  const pad = 20;

  const xy = points.map((point, index) => {
    const x = pad + (index / Math.max(1, points.length - 1)) * (width - pad * 2);
    const y = max === min ? height / 2 : height - pad - ((point.value - min) / (max - min)) * (height - pad * 2);
    return { x, y, ...point };
  });

  const path = xy.map((point, index) => `${index === 0 ? "M" : "L"}${point.x} ${point.y}`).join(" ");

  return (
    <div className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">{title}</p>
      <div className="mt-3 overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[560px]">
          <path d={path} fill="none" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" />
          {xy.map((point) => (
            <g key={`${point.label}-${point.x}`}>
              <circle cx={point.x} cy={point.y} r="4" fill="var(--navy)" />
              <text x={point.x} y={height - 2} textAnchor="middle" fontSize="10" fill="var(--muted)">
                {point.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
