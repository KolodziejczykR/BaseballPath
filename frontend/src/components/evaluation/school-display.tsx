"use client";

import type { ReactNode } from "react";

// Shared types, helpers, and presentational components for rendering a School
// in both the live evaluation report (`/evaluations/[runId]`) and the saved
// schools shortlist (`/saved-schools`). Both pages persist the same School
// shape (the saved page reads it from `saved_schools.school_data`), so they
// can share the same display building blocks.

export type SchoolLocation = {
  state?: string;
  region?: string;
  latitude?: number;
  longitude?: number;
};

export type MetricComparison = {
  metric: string;
  player_value: number;
  division_avg: number;
  unit: string;
};

export type ResearchSource = {
  label?: string;
  url?: string;
  source_type?: string;
};

export type School = {
  rank?: number;
  school_name: string;
  display_school_name?: string;
  school_logo_image?: string | null;
  conference?: string;
  division_group?: string;
  division_label?: string;
  baseball_division?: number;
  location?: SchoolLocation;
  baseball_fit?: string;
  fit_label?: string;
  delta?: number;
  sci?: number;
  trend?: string;
  academic_fit?: string;
  academic_selectivity_score?: string;
  estimated_annual_cost?: number | null;
  metric_comparisons?: MetricComparison[];
  fit_summary?: string;
  why_this_school?: string;
  research_confidence?: string;
  opportunity_fit?: string;
  overall_school_view?: string;
  roster_label?: string;
  review_adjustment_from_base?: string;
  ranking_adjustment?: number;
  ranking_score?: number;
  research_status?: string;
  research_data_gaps?: string[];
  research_sources?: ResearchSource[];
  baseball_record?: string | null;
  baseball_wins?: number | null;
  baseball_losses?: number | null;
  school_city?: string | null;
  undergrad_enrollment?: number | null;
};

const FIT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  fit: { bg: "rgba(107,143,94,0.15)", text: "var(--sage-green)", border: "var(--sage-green)" },
  reach: { bg: "rgba(184,115,51,0.15)", text: "var(--copper)", border: "var(--copper)" },
  safety: { bg: "rgba(212,168,67,0.15)", text: "var(--golden-sand)", border: "var(--golden-sand)" },
};

export const MEDAL_COLORS = ["#D4A843", "#C0C0C0", "#CD7F32"];

export function getNcaLogoUrl(logoKey: string | null | undefined): string | null {
  const key = (logoKey || "").trim();
  if (!key) return null;
  return `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(key)}.svg`;
}

export function getSchoolDedupeKey(school: Pick<School, "school_name" | "school_logo_image">): string {
  const logoKey = (school.school_logo_image || "").trim().toLowerCase();
  if (logoKey) return `logo:${logoKey}`;
  return `name:${school.school_name.trim().toLowerCase()}`;
}

export function formatCost(cost: number | null | undefined): string {
  if (cost == null) return "N/A";
  return `$${cost.toLocaleString()}/yr`;
}

export function fitLabel(fit: string | undefined): string {
  if (!fit) return "";
  return fit.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function fitColorKey(fit: string | undefined): string {
  const lower = (fit || "").toLowerCase();
  if (lower.includes("safety")) return "safety";
  if (lower.includes("reach")) return "reach";
  return "fit";
}

export function schoolDivisionLabel(school: School | undefined): string {
  if (!school) return "";
  if (school.division_label) return school.division_label;
  if (school.division_group?.includes("Power 4")) return "Power 4";
  if (school.division_group?.includes("Non-P4")) return "Division 1";
  if (school.baseball_division === 2) return "Division 2";
  if (school.baseball_division === 3) return "Division 3";
  return "";
}

export function baseballFitText(school: School): string {
  if (school.fit_label) return school.fit_label;
  return fitLabel(school.baseball_fit);
}

export function schoolDisplayName(school: Pick<School, "display_school_name" | "school_name">): string {
  return school.display_school_name || school.school_name;
}

export function FitBadge({ type, label }: { type: string; label: string }) {
  const colors = FIT_COLORS[fitColorKey(type)] || FIT_COLORS.fit;
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
      style={{ background: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
    >
      {label}
    </span>
  );
}

// Stoplight semantics — Open is good, Competitive is contested, Crowded is
// the most important warning ("no roster room"). Always prefixed with
// "Roster:" so it doesn't read as an unlabeled category sitting next to the
// labeled Baseball/Academic fit badges.
export function RosterBadge({ label }: { label: string | undefined }) {
  if (!label || label === "unknown") return null;
  const isOpen = label === "open";
  const isCrowded = label === "crowded";
  const text = isOpen ? "Open" : isCrowded ? "Crowded" : "Competitive";
  // Open = green, Competitive = amber, Crowded = red.
  const bg = isOpen ? "#dcfce7" : isCrowded ? "#fee2e2" : "#fef3c7";
  const color = isOpen ? "#166534" : isCrowded ? "#b91c1c" : "#92400e";
  const border = isOpen ? "#86efac" : isCrowded ? "#fca5a5" : "#fcd34d";
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
      style={{ background: bg, color, border: `1px solid ${border}` }}
    >
      Roster: {text}
    </span>
  );
}

export function MetricComparisonTable({ comparisons }: { comparisons: MetricComparison[] | undefined }) {
  if (!comparisons || comparisons.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-[var(--stroke)]">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-[var(--sand)]/40">
            <th className="px-3 py-2 text-left font-semibold text-[var(--muted)]">Metric</th>
            <th className="px-3 py-2 text-right font-semibold text-[var(--muted)]">You</th>
            <th className="px-3 py-2 text-right font-semibold text-[var(--muted)]">Div. Avg</th>
            <th className="px-3 py-2 text-right font-semibold text-[var(--muted)]">Diff</th>
          </tr>
        </thead>
        <tbody>
          {comparisons.map((m) => {
            const diff = m.player_value - m.division_avg;
            const isPositive = diff > 0;
            // For time-based metrics (sec), lower is better.
            const isTimeBased = m.unit === "sec";
            const isGood = isTimeBased ? diff < 0 : diff > 0;
            // Sub-second metrics need 2 decimals so 1.9/2.0/-0.1 don't read sloppy.
            const decimals = m.metric === "60-Yard Dash" || m.metric === "Pop Time" ? 2 : 1;

            return (
              <tr key={m.metric} className="border-t border-[var(--stroke)]/50">
                <td className="px-3 py-1.5 font-medium text-[var(--foreground)]">{m.metric}</td>
                <td className="px-3 py-1.5 text-right font-semibold text-[var(--navy)]">
                  {m.player_value.toFixed(decimals)} {m.unit}
                </td>
                <td className="px-3 py-1.5 text-right text-[var(--muted)]">
                  {m.division_avg.toFixed(decimals)} {m.unit}
                </td>
                <td
                  className="px-3 py-1.5 text-right font-semibold"
                  style={{ color: isGood ? "var(--sage-green)" : "var(--copper)" }}
                >
                  {isPositive ? "+" : ""}
                  {diff.toFixed(decimals)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function SchoolHeader({ school, showRankMedal = true }: { school: School; showRankMedal?: boolean }) {
  const logoUrl = getNcaLogoUrl(school.school_logo_image);
  const rank = school.rank;
  const showMedal = showRankMedal && rank != null && rank >= 1 && rank <= 3;

  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {showMedal && (
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
              style={{ background: MEDAL_COLORS[rank! - 1] }}
            >
              {rank}
            </span>
          )}
          <h2 className="text-lg font-bold text-[var(--foreground)]">{schoolDisplayName(school)}</h2>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
          {school.conference && <span>{school.conference}</span>}
          {school.conference && school.location?.state && <span>&middot;</span>}
          {school.location?.state && <span>{school.location.state}</span>}
          {school.location?.region && (
            <>
              <span>&middot;</span>
              <span>{school.location.region}</span>
            </>
          )}
        </div>
      </div>
      {logoUrl && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={logoUrl}
            alt=""
            onError={(e) => { e.currentTarget.style.display = "none"; }}
            className="h-14 w-14 shrink-0 rounded-lg border border-[var(--stroke)] bg-white/90 p-1.5 object-contain"
          />
        </>
      )}
    </div>
  );
}

export function SchoolFitBadges({ school }: { school: School }) {
  const division = schoolDivisionLabel(school);
  return (
    <div className="flex flex-wrap gap-2">
      {division && (
        <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
          {division}
        </span>
      )}
      {school.baseball_fit && (
        <FitBadge
          type={school.fit_label || school.baseball_fit}
          label={`Baseball: ${baseballFitText(school)}`}
        />
      )}
      {school.academic_fit && (
        <FitBadge type={school.academic_fit} label={`Academic: ${fitLabel(school.academic_fit)}`} />
      )}
      <RosterBadge label={school.roster_label} />
    </div>
  );
}

export function SchoolStatsGrid({ school }: { school: School }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {school.academic_selectivity_score && (
        <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
          <p className="text-xs text-[var(--muted)]">Academic Score</p>
          <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">{school.academic_selectivity_score}</p>
        </div>
      )}
      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
        <p className="text-xs text-[var(--muted)]">Est. annual cost</p>
        <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">{formatCost(school.estimated_annual_cost)}</p>
      </div>
    </div>
  );
}

export function WhyThisSchoolCard({ school }: { school: School }) {
  const text = school.why_this_school || school.fit_summary;
  if (!text) return null;
  return (
    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Why this school</p>
      <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">{text}</p>
    </div>
  );
}

export function ResearchSourcesCard({ sources }: { sources: ResearchSource[] | undefined }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Research sources</p>
      <ul className="mt-2 space-y-1 text-sm">
        {sources.map((source) => (
          <li key={`${source.url}-${source.label}`}>
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--primary)] hover:underline"
            >
              {source.label || source.url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MetricComparisonsSection({ school }: { school: School }) {
  if (!school.metric_comparisons || school.metric_comparisons.length === 0) return null;
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
        Your metrics vs. {schoolDivisionLabel(school) || "division"} average
      </p>
      <MetricComparisonTable comparisons={school.metric_comparisons} />
    </div>
  );
}

export function formatBaseballRecord(school: School): string {
  if (school.baseball_record) return school.baseball_record;
  if (school.baseball_wins != null && school.baseball_losses != null) {
    return `${school.baseball_wins}-${school.baseball_losses}`;
  }
  return "—";
}

export function formatEnrollment(school: School): string {
  if (school.undergrad_enrollment == null) return "—";
  return `${school.undergrad_enrollment.toLocaleString()} undergrads`;
}

export function formatLocation(school: School): string {
  const city = school.school_city?.trim();
  const state = school.location?.state?.trim();
  if (city && state) return `${city}, ${state}`;
  if (city) return city;
  if (state) return state;
  return "—";
}

// Side-by-side comparison of two saved/evaluated schools.
export function SchoolCompareCard({ schools }: { schools: [School, School] }) {
  const [a, b] = schools;
  const rows: { label: string; a: ReactNode; b: ReactNode }[] = [
    {
      label: "Division",
      a: schoolDivisionLabel(a) || "—",
      b: schoolDivisionLabel(b) || "—",
    },
    {
      label: "Baseball fit",
      a: a.baseball_fit ? (
        <FitBadge type={a.fit_label || a.baseball_fit} label={baseballFitText(a) || "—"} />
      ) : (
        "—"
      ),
      b: b.baseball_fit ? (
        <FitBadge type={b.fit_label || b.baseball_fit} label={baseballFitText(b) || "—"} />
      ) : (
        "—"
      ),
    },
    {
      label: "Academic fit",
      a: a.academic_fit ? <FitBadge type={a.academic_fit} label={fitLabel(a.academic_fit)} /> : "—",
      b: b.academic_fit ? <FitBadge type={b.academic_fit} label={fitLabel(b.academic_fit)} /> : "—",
    },
    {
      label: "Roster outlook",
      a: a.roster_label && a.roster_label !== "unknown" ? <RosterBadge label={a.roster_label} /> : "—",
      b: b.roster_label && b.roster_label !== "unknown" ? <RosterBadge label={b.roster_label} /> : "—",
    },
    {
      label: "Est. annual cost",
      a: formatCost(a.estimated_annual_cost),
      b: formatCost(b.estimated_annual_cost),
    },
    {
      label: "Location",
      a: formatLocation(a),
      b: formatLocation(b),
    },
    {
      label: "Undergrad enrollment",
      a: formatEnrollment(a),
      b: formatEnrollment(b),
    },
    {
      label: "Last season record",
      a: formatBaseballRecord(a),
      b: formatBaseballRecord(b),
    },
  ];

  function ColumnHeader({ school }: { school: School }) {
    const logoUrl = getNcaLogoUrl(school.school_logo_image);
    return (
      <div className="flex items-start gap-3">
        {logoUrl && (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={logoUrl}
              alt=""
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
              className="h-12 w-12 shrink-0 rounded-lg border border-[var(--stroke)] bg-white/90 p-1.5 object-contain"
            />
          </>
        )}
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-[var(--foreground)]">{schoolDisplayName(school)}</p>
          {school.conference && (
            <p className="mt-0.5 truncate text-xs text-[var(--muted)]">{school.conference}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-5 shadow-soft">
      <div className="grid grid-cols-[minmax(7rem,auto)_minmax(0,1fr)_minmax(0,1fr)] gap-x-4 gap-y-3">
        <div />
        <ColumnHeader school={a} />
        <ColumnHeader school={b} />

        {rows.map((row, idx) => (
          <div
            key={row.label}
            className={`contents ${idx % 2 === 1 ? "compare-row-alt" : ""}`}
          >
            <p className="border-t border-[var(--stroke)]/60 pt-3 text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
              {row.label}
            </p>
            <div className="border-t border-[var(--stroke)]/60 pt-3 text-sm font-semibold text-[var(--foreground)]">
              {row.a}
            </div>
            <div className="border-t border-[var(--stroke)]/60 pt-3 text-sm font-semibold text-[var(--foreground)]">
              {row.b}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Compact card used in the school list (left column on both pages).
export function SchoolListCard({
  school,
  isActive,
  onSelect,
  showFitBadges = true,
  showRankMedal = true,
  selectionMode,
  isSelected,
  isSelectable = true,
}: {
  school: School;
  isActive: boolean;
  onSelect: () => void;
  showFitBadges?: boolean;
  showRankMedal?: boolean;
  // When provided, the card renders a checkbox indicator and uses the selection
  // border treatment instead of the "active" treatment.
  selectionMode?: boolean;
  isSelected?: boolean;
  // When false in selection mode, the card is dimmed and unclickable
  // (e.g. compare-cap reached).
  isSelectable?: boolean;
}) {
  const logoUrl = getNcaLogoUrl(school.school_logo_image);
  const rank = school.rank;
  const showMedal = showRankMedal && rank != null && rank >= 1 && rank <= 3;
  const tierLabel = schoolDivisionLabel(school);

  const disabled = selectionMode && !isSelectable && !isSelected;
  const borderClass = selectionMode
    ? isSelected
      ? "border-[var(--primary)] ring-1 ring-[var(--primary)] bg-[var(--primary)]/[0.04]"
      : disabled
        ? "border-[var(--stroke)] opacity-50"
        : "border-[var(--stroke)] hover:-translate-y-0.5 hover:border-[var(--primary)]/40"
    : isActive
      ? "border-[var(--primary)] ring-1 ring-[var(--primary)]"
      : "border-[var(--stroke)] hover:-translate-y-0.5 hover:border-[var(--primary)]/40";

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      aria-pressed={selectionMode ? Boolean(isSelected) : undefined}
      className={`w-full rounded-2xl border bg-white/80 p-4 text-left shadow-soft transition-all duration-200 ${borderClass} ${
        disabled ? "cursor-not-allowed" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {selectionMode && (
              <span
                aria-hidden
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border text-[10px] font-bold ${
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                    : "border-[var(--stroke)] bg-white text-transparent"
                }`}
              >
                ✓
              </span>
            )}
            {!selectionMode && showMedal && (
              <span
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                style={{ background: MEDAL_COLORS[rank! - 1] }}
              >
                {rank}
              </span>
            )}
            {!selectionMode && showRankMedal && rank != null && !showMedal && (
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--sand)] text-xs font-semibold text-[var(--navy)]">
                {rank}
              </span>
            )}
            <p className="text-sm font-semibold text-[var(--foreground)] md:text-base">{schoolDisplayName(school)}</p>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            {tierLabel && (
              <span className="rounded-full bg-[var(--sand)] px-2.5 py-0.5 text-xs font-semibold text-[var(--navy)]">
                {tierLabel}
              </span>
            )}
            {school.conference && <span className="text-xs text-[var(--muted)]">{school.conference}</span>}
            {school.location?.state && <span className="text-xs text-[var(--muted)]">{school.location.state}</span>}
          </div>

          {showFitBadges && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {school.baseball_fit && (
                <FitBadge
                  type={school.fit_label || school.baseball_fit}
                  label={`Baseball: ${baseballFitText(school)}`}
                />
              )}
              {school.academic_fit && (
                <FitBadge type={school.academic_fit} label={`Academic: ${fitLabel(school.academic_fit)}`} />
              )}
              <RosterBadge label={school.roster_label} />
            </div>
          )}
        </div>

        {logoUrl && (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={logoUrl}
              alt=""
              loading="lazy"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
              className="h-12 w-12 shrink-0 rounded-lg border border-[var(--stroke)] bg-white/90 p-1.5 object-contain"
            />
          </>
        )}
      </div>
    </button>
  );
}
