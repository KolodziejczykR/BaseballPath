"use client";

import { useEffect, useRef } from "react";
import { PlayerCardBack } from "@/components/player-card/player-card-back";
import { PlayerCardContainer } from "@/components/player-card/player-card-container";
import { PlayerCardFront } from "@/components/player-card/player-card-front";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type PublicCardData = {
  slug?: string;
  display_name: string;
  class_year?: number | null;
  primary_position?: string | null;
  stats_snapshot?: Record<string, number>;
  prediction_level?: string | null;
  d1_probability?: number | null;
  p4_probability?: number | null;
  video_links?: Array<{ url: string; label: string; platform?: string }>;
  preferences?: Record<string, string>;
  photo_url?: string | null;
  bp_profile_link?: string | null;
};

function toRows(position: string | null | undefined, stats: Record<string, number>) {
  const positionUpper = (position || "").toUpperCase();
  const keys =
    positionUpper.includes("HP")
      ? [
          ["FB Max", "fastball_velo_max", "mph"],
          ["FB Avg", "fastball_velo_range", "mph"],
          ["FB Spin", "fastball_spin", "rpm"],
          ["CH Velo", "changeup_velo", "mph"],
          ["CB Velo", "curveball_velo", "mph"],
          ["SL Velo", "slider_velo", "mph"],
        ]
      : [
          ["Exit Velo", "exit_velo_max", "mph"],
          ["Throw Velo", positionUpper === "OF" ? "of_velo" : positionUpper === "C" ? "c_velo" : "inf_velo", "mph"],
          ["Pop Time", "pop_time", "sec"],
          ["60 Time", "sixty_time", "sec"],
          ["Height", "height", "in"],
          ["Weight", "weight", "lb"],
        ];

  const rows: Array<{ label: string; value: string | number; unit?: string }> = [];
  for (const [label, key, unit] of keys) {
    const value = stats[key as string];
    if (value === null || value === undefined) continue;
    rows.push({ label, value, unit });
  }
  return rows;
}

export function PublicCardClient({ card }: { card: PublicCardData }) {
  const stats = toRows(card.primary_position, card.stats_snapshot || {});
  const clickRecorded = useRef(false);

  useEffect(() => {
    if (!card.slug || clickRecorded.current) return;
    clickRecorded.current = true;
    fetch(`${API_BASE_URL}/p/${card.slug}/click`, { method: "POST" }).catch(() => {
      /* click tracking is best-effort — swallow errors */
    });
  }, [card.slug]);

  return (
    <div className="mt-8 flex flex-col items-center gap-6">
      <PlayerCardContainer
        front={
          <PlayerCardFront
            displayName={card.display_name}
            position={card.primary_position || "-"}
            classYear={card.class_year || undefined}
            photoUrl={card.photo_url || undefined}
            stats={stats}
          />
        }
        back={
          <PlayerCardBack
            predictionLevel={card.prediction_level || "Prospect"}
            d1Probability={card.d1_probability || 0}
            p4Probability={card.p4_probability || null}
            videoLinks={card.video_links || []}
            visiblePreferences={card.preferences || {}}
            profileLink={card.bp_profile_link || undefined}
          />
        }
      />

      <a
        href="https://baseballpath.com"
        className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong"
      >
        Build your own Player Card on BaseballPath
      </a>
    </div>
  );
}
