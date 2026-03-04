"use client";

type LeverageRankCardProps = {
  rank: number;
  statName: string;
  displayName: string;
  unit: string;
  currentValue: number;
  maxImpact: number;
  steps: Array<{
    delta: number;
    new_value: number;
    new_probability: number;
    probability_change: number;
  }>;
};

function impactColor(maxImpact: number): string {
  const pct = Math.abs(maxImpact);
  if (pct >= 0.08) return "bg-[var(--primary)]";
  if (pct >= 0.03) return "bg-[var(--accent)]";
  return "bg-[var(--muted)]";
}

export function LeverageRankCard({ rank, statName, displayName, unit, currentValue, maxImpact, steps }: LeverageRankCardProps) {
  const largestStep =
    steps.length > 0
      ? steps.reduce((best, next) => (Math.abs(next.probability_change) > Math.abs(best.probability_change) ? next : best), steps[0])
      : null;

  return (
    <div className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-4 shadow-soft">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--navy)] text-sm font-bold text-white">#{rank}</div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[var(--navy)]">{displayName}</p>
          <p className="text-xs text-[var(--muted)]">
            {statName} · Current: {currentValue} {unit}
          </p>

          <div className="mt-3">
            <div className="h-2 rounded-full bg-[var(--sand)]/70">
              <div className={`h-full rounded-full ${impactColor(maxImpact)}`} style={{ width: `${Math.min(Math.abs(maxImpact) * 1000, 100)}%` }} />
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">Max impact: {(maxImpact * 100).toFixed(1)}%</p>
          </div>

          {largestStep ? (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Best step: {largestStep.delta > 0 ? "+" : ""}
              {largestStep.delta} {unit} -&gt; {(largestStep.new_probability * 100).toFixed(1)}% ({(largestStep.probability_change * 100).toFixed(1)}%)
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
