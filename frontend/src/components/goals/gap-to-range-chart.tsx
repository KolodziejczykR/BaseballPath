"use client";

type GapToRangeChartProps = {
  stats: Array<{
    statName: string;
    displayName: string;
    unit: string;
    currentValue: number;
    p10: number;
    p25: number;
    median: number;
    p75: number;
    p90: number;
  }>;
};

function pct(min: number, max: number, value: number): number {
  if (max <= min) return 50;
  const raw = ((value - min) / (max - min)) * 100;
  return Math.max(0, Math.min(100, raw));
}

function markerColor(current: number, p25: number, p75: number): string {
  if (current < p25) return "bg-[var(--accent)]";
  if (current > p75) return "bg-[var(--sand)]";
  return "bg-[var(--primary)]";
}

export function GapToRangeChart({ stats }: GapToRangeChartProps) {
  return (
    <div className="space-y-4">
      {stats.length === 0 ? <p className="text-sm text-[var(--muted)]">No reference ranges available yet.</p> : null}
      {stats.map((stat) => {
        const min = Math.min(stat.p10, stat.currentValue);
        const max = Math.max(stat.p90, stat.currentValue);
        const p10Left = pct(min, max, stat.p10);
        const p25Left = pct(min, max, stat.p25);
        const medianLeft = pct(min, max, stat.median);
        const p75Left = pct(min, max, stat.p75);
        const p90Left = pct(min, max, stat.p90);
        const markerLeft = pct(min, max, stat.currentValue);

        return (
          <div key={stat.statName} className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--navy)]">{stat.displayName}</p>
              <p className="text-xs text-[var(--muted)]">
                {stat.currentValue} {stat.unit}
              </p>
            </div>

            <div className="relative mt-4 h-8">
              <div className="absolute left-0 right-0 top-3 h-2 rounded-full bg-[var(--sand)]/60" />
              <div
                className="absolute top-3 h-2 rounded-full bg-[var(--primary)]/35"
                style={{ left: `${p25Left}%`, width: `${Math.max(0, p75Left - p25Left)}%` }}
              />
              <div className="absolute top-1 h-6 w-px bg-[var(--muted)]" style={{ left: `${p10Left}%` }} />
              <div className="absolute top-1 h-6 w-px bg-[var(--muted)]" style={{ left: `${p90Left}%` }} />
              <div className="absolute top-0 h-8 w-px bg-[var(--navy)]/60" style={{ left: `${medianLeft}%` }} />
              <div
                className={`absolute top-0 h-8 w-1.5 -translate-x-1/2 rounded-full ${markerColor(stat.currentValue, stat.p25, stat.p75)}`}
                style={{ left: `${markerLeft}%` }}
              />
            </div>

            <div className="mt-2 flex flex-wrap justify-between text-[11px] text-[var(--muted)]">
              <span>p10 {stat.p10}</span>
              <span>p25 {stat.p25}</span>
              <span>p75 {stat.p75}</span>
              <span>p90 {stat.p90}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
