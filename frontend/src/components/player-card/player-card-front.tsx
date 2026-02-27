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
    <div className="relative h-full w-full bg-[#18365a] text-white">
      <div className="absolute inset-0 rounded-2xl border-4 border-transparent bg-[linear-gradient(#18365a,#18365a),conic-gradient(from_0deg,#f28b6a,#f9db68,#83e08f,#66d5e7,#8db2ff,#ee8fe4,#f28b6a)] bg-[padding-box,border-box]" />
      <HolographicEffect />

      <div className="relative z-10 flex h-full flex-col p-3">
        <div className="relative h-[60%] overflow-hidden rounded-xl border border-white/15">
          {photoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={photoUrl} alt={`${displayName} player photo`} className="h-full w-full object-cover" />
          ) : (
            <div className="grid h-full w-full place-items-center bg-gradient-to-br from-[#34557e] to-[#18365a]">
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-white/75">No Photo</p>
            </div>
          )}

          <div className="absolute left-2 top-2 rounded-full bg-[#0f1823]/80 px-3 py-1 text-xs font-semibold">{position}</div>
          {classYear ? (
            <div className="absolute right-2 top-2 rounded-full bg-[#0f1823]/80 px-3 py-1 text-xs font-semibold">&apos;{String(classYear).slice(-2)}</div>
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

        <p className="mt-2 text-center text-[10px] uppercase tracking-[0.34em] text-[#ece1c5]/80">BaseballPath</p>
      </div>
    </div>
  );
}
