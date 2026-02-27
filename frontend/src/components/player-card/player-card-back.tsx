"use client";

type CardBackProps = {
  predictionLevel: string;
  d1Probability: number;
  p4Probability?: number | null;
  videoLinks: Array<{ url: string; label: string; platform?: string }>;
  visiblePreferences: Record<string, string>;
  profileLink?: string;
  shareUrl?: string;
};

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-white/85">
        <span>{label}</span>
        <span className="font-semibold">{pct.toFixed(1)}%</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-white/15">
        <div className="h-full rounded-full bg-[var(--primary)]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function PlayerCardBack({
  predictionLevel,
  d1Probability,
  p4Probability,
  videoLinks,
  visiblePreferences,
  profileLink,
  shareUrl,
}: CardBackProps) {
  return (
    <div className="flex h-full flex-col bg-[#10233d] p-4 text-white">
      <div className="rounded-xl border border-white/15 bg-white/10 p-3 text-center">
        <p className="text-[10px] uppercase tracking-[0.28em] text-white/75">Projection</p>
        <p className="mt-1 text-xl font-bold text-[#ece1c5]">{predictionLevel || "Prospect"}</p>
      </div>

      <div className="mt-4 space-y-3 rounded-xl border border-white/15 bg-white/8 p-3">
        <ProbabilityBar label="D1" value={d1Probability || 0} />
        {typeof p4Probability === "number" ? <ProbabilityBar label="Power 4" value={p4Probability} /> : null}
      </div>

      <div className="mt-4">
        <p className="text-[10px] uppercase tracking-[0.22em] text-white/70">Video Links</p>
        <div className="mt-2 space-y-2">
          {videoLinks.length === 0 ? <p className="text-xs text-white/65">No videos added.</p> : null}
          {videoLinks.slice(0, 3).map((link) => (
            <a
              key={`${link.url}-${link.label}`}
              href={link.url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg border border-white/15 bg-white/6 px-3 py-2 text-xs hover:bg-white/12"
            >
              {link.label || link.platform || "Video"}
            </a>
          ))}
        </div>
      </div>

      <div className="mt-4 flex-1 overflow-hidden">
        <p className="text-[10px] uppercase tracking-[0.22em] text-white/70">Visible Preferences</p>
        <div className="mt-2 space-y-1">
          {Object.entries(visiblePreferences).length === 0 ? <p className="text-xs text-white/65">No preferences shown.</p> : null}
          {Object.entries(visiblePreferences)
            .slice(0, 5)
            .map(([key, value]) => (
              <p key={key} className="truncate text-xs text-white/85">
                <span className="font-semibold">{key}:</span> {value}
              </p>
            ))}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 text-xs">
        {profileLink ? (
          <a href={profileLink} target="_blank" rel="noreferrer" className="rounded-lg border border-white/20 px-3 py-2 text-center hover:bg-white/10">
            View Full Profile
          </a>
        ) : null}
        {shareUrl ? <p className="truncate text-center text-[11px] text-white/65">{shareUrl}</p> : null}
      </div>
    </div>
  );
}
