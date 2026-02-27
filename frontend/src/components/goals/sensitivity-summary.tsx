"use client";

type Ranking = {
  stat_name: string;
  display: string;
  max_impact: number;
};

type SensitivitySummaryProps = {
  baseProbability: number;
  rankings: Ranking[];
};

export function SensitivitySummary({ baseProbability, rankings }: SensitivitySummaryProps) {
  const top = rankings.slice(0, 3);

  return (
    <div className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-5">
      <p className="text-xs uppercase tracking-[0.26em] text-[var(--muted)]">Model Summary</p>
      <p className="mt-2 text-sm text-[var(--navy)]">
        Based on our model&apos;s analysis, your current target-level probability is {(baseProbability * 100).toFixed(1)}%.
      </p>

      <div className="mt-3 space-y-2">
        {top.length === 0 ? <p className="text-sm text-[var(--muted)]">No leverage rankings available yet.</p> : null}
        {top.map((item, index) => (
          <p key={item.stat_name} className="text-sm text-[var(--navy)]">
            {index + 1}. {item.display || item.stat_name} ({(item.max_impact * 100).toFixed(1)}% max delta)
          </p>
        ))}
      </div>
    </div>
  );
}
