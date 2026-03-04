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
  const colorClass = pct >= 60 ? "bg-[var(--sage-green)]" : pct >= 30 ? "bg-[var(--golden-sand)]" : "bg-[var(--burnt-sienna)]";
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-white/85">
        <span className="text-sm font-semibold text-white">{label}</span>
        <span className="font-mono text-sm font-bold text-white">{pct.toFixed(1)}%</span>
      </div>
      <div className="mt-1 h-2.5 rounded-full bg-white/10">
        <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function PlayerCardBack({
  d1Probability,
  p4Probability,
  videoLinks,
  visiblePreferences,
  profileLink,
  shareUrl,
}: CardBackProps) {
  return (
    <div className="flex h-full flex-col bg-[#1A0F08] p-4 text-white hover:bg-[#1A0F08]">
      <div className="mt-0 space-y-3 rounded-xl p-0">
        <p className="text-xs uppercase tracking-[0.2em] text-[#D4A843] mb-3">Projection</p>
        <ProbabilityBar label="D1" value={d1Probability || 0} />
        {typeof p4Probability === "number" ? <ProbabilityBar label="Power 4" value={p4Probability} /> : null}
      </div>

      <div className="mt-3">
        <p className="text-xs uppercase tracking-[0.2em] text-[#D4A843] mb-2">Film</p>
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

      <div className="mt-3 flex-1 overflow-hidden">
        <p className="text-xs uppercase tracking-[0.2em] text-[#D4A843] mb-2">Preferences</p>
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
        {shareUrl ? <p className="truncate text-center text-[11px] text-white/50 border-t border-white/10 pt-2">{shareUrl}</p> : null}
      </div>
    </div>
  );
}
