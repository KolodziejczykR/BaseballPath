"use client";

type CardStatRowProps = {
  label: string;
  value: string | number;
  unit?: string;
};

export function CardStatRow({ label, value, unit }: CardStatRowProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/15 bg-white/8 px-3 py-2">
      <span className="text-[10px] uppercase tracking-[0.14em] text-[#D4A843]/80">{label}</span>
      <span className="text-sm font-semibold text-white">
        {value}
        {unit ? <span className="ml-1 text-xs font-medium text-white/80">{unit}</span> : null}
      </span>
    </div>
  );
}
