"use client";

import { CardStatRow } from "@/components/player-card/card-stat-row";
import { HolographicEffect } from "@/components/player-card/holographic-effect";

type CardFrontProps = {
  displayName: string;
  position: string;
  classYear?: number;
  photoUrl?: string;
  stats: Array<{ label: string; value: string | number; unit?: string }>;
};

export function PlayerCardFront({ displayName, position, classYear, photoUrl, stats }: CardFrontProps) {
  return (
    <div className="relative h-full w-full bg-[#3B2718] text-white">
      <div className="absolute inset-0 rounded-2xl border border-[#B87333]/25 shadow-[inset_0_1px_0_rgba(212,168,67,0.1)]" />
      <HolographicEffect />

      <div className="relative z-10 flex h-full flex-col p-3">
        <div className="relative h-[60%] overflow-hidden rounded-xl border border-white/15">
          {photoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={photoUrl} alt={`${displayName} player photo`} className="h-full w-full object-cover" />
          ) : (
            <div className="grid h-full w-full place-items-center bg-gradient-to-br from-[#3B2718] to-[#2C1810]">
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-white/75">No Photo</p>
            </div>
          )}

          <div className="absolute left-3 top-3 rounded-lg bg-[#D4A843] px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-[#2C1810]">{position}</div>
          {classYear ? (
            <div className="absolute right-3 top-3 text-sm font-mono font-bold text-white/90">&apos;{String(classYear).slice(-2)}</div>
          ) : null}

          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-3 py-2">
            <p className="truncate text-lg font-semibold text-white">{displayName}</p>
          </div>
        </div>

        <div className="mt-3 grid flex-1 grid-cols-2 gap-2">
          {stats.slice(0, 8).map((stat) => (
            <CardStatRow key={`${stat.label}-${stat.value}`} label={stat.label} value={stat.value} unit={stat.unit} />
          ))}
        </div>

        <p className="mt-2 text-center text-[10px] uppercase tracking-[0.34em] text-[#D4A843]/50">BaseballPath</p>
      </div>
    </div>
  );
}
