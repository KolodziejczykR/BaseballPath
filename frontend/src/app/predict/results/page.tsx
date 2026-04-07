"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useOptionalAuth } from "@/hooks/useOptionalAuth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_RETRIES = 5;
const RETRY_DELAYS = [1000, 2000, 3000, 4000, 5000];

// ---------------------------------------------------------------------------
// Types (matches finalize response)
// ---------------------------------------------------------------------------

type MetricComparison = {
  metric: string;
  player_value: number;
  division_avg: number;
  unit: string;
};

type ResearchSource = {
  label?: string;
  url?: string;
  source_type?: string;
};

type School = {
  rank: number;
  school_name: string;
  display_school_name?: string;
  school_logo_image?: string | null;
  conference?: string;
  division_group?: string;
  division_label?: string;
  baseball_division?: number;
  location?: { state?: string; region?: string };
  baseball_fit?: string;
  fit_label?: string;
  academic_fit?: string;
  niche_academic_grade?: string;
  estimated_annual_cost?: number | null;
  metric_comparisons?: MetricComparison[];
  fit_summary?: string;
  school_description?: string;
  roster_summary?: string;
  opportunity_summary?: string;
  trend_summary?: string;
  research_confidence?: string;
  opportunity_fit?: string;
  overall_school_view?: string;
  roster_label?: string;
  ranking_adjustment?: number;
  research_reasons?: string[];
  research_risks?: string[];
  research_data_gaps?: string[];
  research_sources?: ResearchSource[];
};

type BaseballAssessment = {
  predicted_tier?: string;
  within_tier_percentile?: number;
  d1_probability?: number;
  p4_probability?: number;
  confidence?: string;
};

type AcademicScore = {
  composite?: number;
  gpa_rating?: number;
  test_rating?: number;
  ap_rating?: number;
};

type FinalizeResult = {
  run_id: string;
  disclaimer?: string;
  baseball_assessment?: BaseballAssessment;
  academic_assessment?: AcademicScore;
  schools?: School[];
  llm_reasoning_status?: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FIT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  fit: { bg: "rgba(107,143,94,0.15)", text: "var(--sage-green)", border: "var(--sage-green)" },
  reach: { bg: "rgba(184,115,51,0.15)", text: "var(--copper)", border: "var(--copper)" },
  safety: { bg: "rgba(212,168,67,0.15)", text: "var(--golden-sand)", border: "var(--golden-sand)" },
};

function getNcaLogoUrl(logoKey: string | null | undefined): string | null {
  const key = (logoKey || "").trim();
  if (!key) return null;
  return `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(key)}.svg`;
}

function tierDisplayLabel(tier: string | undefined): string {
  if (!tier) return "Unknown";
  if (tier.includes("Power 4")) return "Power 4";
  if (tier.includes("Non-P4")) return "Division 1";
  if (tier.includes("Non-D1")) return "Non-D1";
  return tier;
}

function schoolDivisionLabel(school: School): string {
  if (school.division_label) return school.division_label;
  if (school.division_group?.includes("Power 4")) return "Power 4";
  if (school.division_group?.includes("Non-P4")) return "Division 1";
  if (school.baseball_division === 2) return "Division 2";
  if (school.baseball_division === 3) return "Division 3";
  return "";
}

function fitColorKey(fit: string | undefined): string {
  const lower = (fit || "").toLowerCase();
  if (lower.includes("safety")) return "safety";
  if (lower.includes("reach")) return "reach";
  return "fit";
}

function baseballFitText(school: School): string {
  if (school.fit_label) return school.fit_label;
  if (!school.baseball_fit) return "";
  return school.baseball_fit.charAt(0).toUpperCase() + school.baseball_fit.slice(1);
}

function schoolDisplayName(school: School): string {
  return school.display_school_name || school.school_name;
}

function schoolSelectionKey(school: School): string {
  const logoKey = (school.school_logo_image || "").trim().toLowerCase();
  if (logoKey) return `logo:${logoKey}`;
  return `name:${school.school_name.trim().toLowerCase()}`;
}

function formatCost(cost: number | null | undefined): string {
  if (cost == null) return "N/A";
  return `$${cost.toLocaleString()}/yr`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ResultsPage() {
  const { loading: authLoading, accessToken, isAuthenticated } = useOptionalAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [purchaseId, setPurchaseId] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [status, setStatus] = useState("Confirming your payment...");
  const [error, setError] = useState("");
  const [results, setResults] = useState<FinalizeResult | null>(null);
  const [expandedSchoolKey, setExpandedSchoolKey] = useState<string | null>(null);
  const initiated = useRef(false);

  // Read params (localStorage only available client-side)
  useEffect(() => {
    setPurchaseId(searchParams.get("purchase_id") || "");
    setSessionToken(searchParams.get("session_token") || localStorage.getItem("bp_session_token") || "");
  }, [searchParams]);

  useEffect(() => {
    if (authLoading || !purchaseId || !sessionToken || initiated.current) return;
    initiated.current = true;

    async function finalize(attempt: number): Promise<void> {
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (accessToken) {
          headers["Authorization"] = `Bearer ${accessToken}`;
        }

        const res = await fetch(`${API}/evaluate/finalize`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            session_token: sessionToken,
            purchase_id: purchaseId,
          }),
        });

        if (res.status === 402 && attempt < MAX_RETRIES) {
          setStatus(`Waiting for payment confirmation... (${attempt + 1}/${MAX_RETRIES})`);
          await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]));
          return finalize(attempt + 1);
        }

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "Failed to finalize evaluation");
        }

        const data = (await res.json()) as FinalizeResult;

        // Authenticated users: clean up and redirect to the full evaluation detail page
        if (isAuthenticated) {
          localStorage.removeItem("bp_session_token");
          localStorage.removeItem("bp_purchase_id");
          router.replace(`/evaluations/${data.run_id}`);
          return;
        }

        // Anonymous users: store purchase_id for claim flow, show results inline
        if (purchaseId) {
          localStorage.setItem("bp_purchase_id", purchaseId);
        }
        setResults(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    }

    setStatus("Generating your personalized results...");
    finalize(0);
  }, [authLoading, accessToken, isAuthenticated, purchaseId, sessionToken, router]);

  useEffect(() => {
    if (!results?.run_id || results.llm_reasoning_status !== "processing" || !purchaseId || !sessionToken) {
      return;
    }

    let cancelled = false;
    const intervalId = window.setInterval(async () => {
      try {
        const response = await fetch(
          `${API}/evaluate/result?run_id=${encodeURIComponent(results.run_id)}&purchase_id=${encodeURIComponent(purchaseId)}&session_token=${encodeURIComponent(sessionToken)}`
        );
        const data = (await response.json()) as FinalizeResult | { detail?: string };
        if (!response.ok || cancelled) return;
        setResults(data as FinalizeResult);
        if ((data as FinalizeResult).llm_reasoning_status !== "processing") {
          window.clearInterval(intervalId);
        }
      } catch {
        // Keep polling; background enrichment is best-effort.
      }
    }, 8000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [results?.run_id, results?.llm_reasoning_status, purchaseId, sessionToken]);

  // Missing params
  if (!purchaseId || !sessionToken) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-md rounded-3xl border border-red-300 bg-red-50 p-8 text-center">
          <p className="text-sm text-red-700">
            Missing payment or session information. Please{" "}
            <a href="/predict" className="underline">start a new evaluation</a>.
          </p>
        </div>
      </div>
    );
  }

  // Loading / processing state
  if (!results && !error) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-md rounded-3xl border border-[var(--stroke)] bg-white/80 p-8 text-center space-y-4">
          {error ? (
            <>
              <p className="text-sm text-red-700">{error}</p>
              <a
                href="/predict"
                className="inline-block rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold !text-white"
              >
                Start Over
              </a>
            </>
          ) : (
            <>
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
              <p className="text-sm text-[var(--muted)]">{status}</p>
              <p className="text-xs text-[var(--muted)]">
                This may take a moment while we generate AI-personalized insights for your schools.
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-md rounded-3xl border border-red-300 bg-red-50 p-8 text-center space-y-4">
          <p className="text-sm text-red-700">{error}</p>
          <a
            href="/predict"
            className="inline-block rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold !text-white"
          >
            Start Over
          </a>
        </div>
      </div>
    );
  }

  // Results display (anonymous users)
  const baseball = results?.baseball_assessment;
  const academic = results?.academic_assessment;
  const schools = results?.schools || [];
  const llmStatus = results?.llm_reasoning_status;

  return (
    <div className="min-h-screen">
      <main className="px-6 pt-5 pb-10 md:pt-6 md:pb-12">
        <div className="mx-auto max-w-4xl">
          {/* Header */}
          <div className="text-center">
            <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Your Evaluation</p>
            <h1 className="display-font mt-3 text-3xl md:text-4xl">Your Results</h1>
          </div>

          {/* Create account CTA */}
          <div className="mt-6 rounded-2xl border-2 border-[var(--primary)]/30 bg-[var(--primary)]/5 p-5 text-center">
            <p className="text-sm font-semibold text-[var(--foreground)]">
              Create a free account to save your results
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Your results will be saved so you can access them anytime.
              Your next evaluation will be just $29.
            </p>
            <a
              href={`/signup?next=${encodeURIComponent(`/predict/claim-results?session_token=${sessionToken}&purchase_id=${purchaseId}&run_id=${results?.run_id}`)}`}
              className="mt-3 inline-block rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold !text-white"
            >
              Create Free Account
            </a>
            <p className="mt-2 text-xs text-[var(--muted)]">
              Already have an account?{" "}
              <a
                href={`/login?next=${encodeURIComponent(`/predict/claim-results?session_token=${sessionToken}&purchase_id=${purchaseId}&run_id=${results?.run_id}`)}`}
                className="underline text-[var(--primary)]"
              >
                Log in
              </a>
            </p>
          </div>

          {/* Disclaimer */}
          {results?.disclaimer && (
            <div
              className="mt-6 rounded-2xl border p-4"
              style={{
                background: "rgba(212,168,67,0.08)",
                borderColor: "rgba(212,168,67,0.25)",
              }}
            >
              <div className="flex items-start gap-3">
                <span className="mt-0.5 text-lg" style={{ color: "var(--golden-sand)" }}>
                  &#9888;
                </span>
                <div>
                  <p className="text-sm font-semibold" style={{ color: "var(--walnut)" }}>
                    Important disclaimer
                  </p>
                  <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
                    {results.disclaimer}
                  </p>
                </div>
              </div>
            </div>
          )}

          {llmStatus === "processing" && (
            <div className="mt-10 flex flex-col items-center justify-center py-16">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-[var(--stroke)] border-t-[var(--primary)]" />
              <p className="mt-5 text-base font-semibold text-[var(--foreground)]">
                Researching rosters and recruiting context
              </p>
              <p className="mt-2 max-w-md text-center text-sm text-[var(--muted)]">
                We&apos;re analyzing roster depth, incoming recruits, transfers, and positional need for each school. This typically takes 5&ndash;10 minutes.
              </p>
            </div>
          )}

          {llmStatus === "failed" && (
            <div className="mt-6 rounded-2xl border border-red-300 bg-red-50 p-4">
              <p className="text-sm font-semibold text-red-700">
                Deep roster research did not complete.
              </p>
              <p className="mt-1 text-xs text-red-700">
                The current list still reflects the base athletic and academic match.
              </p>
            </div>
          )}

          {/* Assessment summary + schools — hidden while research is running */}
          {llmStatus !== "processing" && <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {/* Baseball */}
            <div className="glass rounded-2xl p-5 shadow-soft">
              <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">Baseball Assessment</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--foreground)]">
                {tierDisplayLabel(baseball?.predicted_tier)}
              </p>
              <div className="mt-3 space-y-1 text-sm text-[var(--muted)]">
                {baseball?.within_tier_percentile != null && (
                  <p>{baseball.within_tier_percentile.toFixed(0)}th percentile within tier</p>
                )}
                {baseball?.d1_probability != null && (
                  <p>D1 probability: {(baseball.d1_probability * 100).toFixed(0)}%</p>
                )}
                {baseball?.confidence && <p>Confidence: {baseball.confidence}</p>}
              </div>
            </div>

            {/* Academic */}
            <div className="glass rounded-2xl p-5 shadow-soft">
              <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">Academic Profile</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--foreground)]">
                {academic?.composite != null ? `${academic.composite.toFixed(0)}/100` : "N/A"}
              </p>
              <div className="mt-3 space-y-1 text-sm text-[var(--muted)]">
                {academic?.gpa_rating != null && <p>GPA rating: {academic.gpa_rating.toFixed(0)}/100</p>}
                {academic?.test_rating != null && <p>Test score rating: {academic.test_rating.toFixed(0)}/100</p>}
                {academic?.ap_rating != null && <p>AP/Honors rating: {academic.ap_rating.toFixed(0)}/100</p>}
              </div>
            </div>
          </div>

          {/* School matches */}
          <div className="mt-8">
            <p className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
              Your Top School Matches
            </p>

            <div className="mt-4 space-y-3">
              {schools.map((school) => {
                const selectionKey = schoolSelectionKey(school);
                const isExpanded = expandedSchoolKey === selectionKey;
                const fitColors = FIT_COLORS[fitColorKey(school.fit_label || school.baseball_fit)] || FIT_COLORS.fit;
                const logoUrl = getNcaLogoUrl(school.school_logo_image);
                const schoolTierLabel = schoolDivisionLabel(school);
                const schoolMeta = school.conference || schoolTierLabel;

                return (
                  <div
                    key={selectionKey}
                    className="glass rounded-2xl shadow-soft overflow-hidden"
                  >
                    {/* Header row — always visible */}
                    <button
                      type="button"
                      onClick={() => setExpandedSchoolKey(isExpanded ? null : selectionKey)}
                      className="w-full px-5 py-4 flex items-center gap-4 text-left"
                    >
                      {/* Rank */}
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                        style={{
                          background: school.rank <= 3
                            ? ["#D4A843", "#C0C0C0", "#CD7F32"][school.rank - 1]
                            : "var(--clay-mist)",
                          color: school.rank <= 3 ? "white" : "var(--muted)",
                        }}
                      >
                        {school.rank}
                      </span>

                      {/* Logo + name */}
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {logoUrl && (
                          <img
                            src={logoUrl}
                            alt=""
                            className="h-8 w-8 shrink-0 object-contain"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                          />
                        )}
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[var(--foreground)] truncate">
                            {schoolDisplayName(school)}
                          </p>
                          {(schoolMeta || school.location?.state) && (
                            <p className="text-xs text-[var(--muted)]">
                              {schoolMeta}
                              {schoolMeta && school.location?.state ? ` · ${school.location.state}` : school.location?.state || ""}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Fit badges */}
                      <div className="flex items-center gap-2 shrink-0">
                        {school.baseball_fit && (
                          <span
                            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                            style={{ background: fitColors.bg, color: fitColors.text, border: `1px solid ${fitColors.border}` }}
                          >
                            {baseballFitText(school)}
                          </span>
                        )}
                        {school.roster_label && school.roster_label !== "unknown" && (
                          <span
                            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                            style={{
                              background: school.roster_label === "open" ? "#dcfce7" : school.roster_label === "crowded" ? "#fef3c7" : "#f3f4f6",
                              color: school.roster_label === "open" ? "#166534" : school.roster_label === "crowded" ? "#92400e" : "#374151",
                              border: `1px solid ${school.roster_label === "open" ? "#86efac" : school.roster_label === "crowded" ? "#fcd34d" : "#d1d5db"}`,
                            }}
                          >
                            {school.roster_label === "open" ? "Open" : school.roster_label === "crowded" ? "Crowded" : "Competitive"}
                          </span>
                        )}
                      </div>

                      {/* Chevron */}
                      <svg
                        className={`h-4 w-4 shrink-0 text-[var(--muted)] transition-transform ${isExpanded ? "rotate-180" : ""}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="px-5 pb-5 space-y-3 border-t border-[var(--stroke)]">
                        {/* Cost + academic */}
                        <div className="pt-3 flex flex-wrap gap-4 text-sm">
                          {school.estimated_annual_cost != null && (
                            <span className="text-[var(--muted)]">Est. cost: <strong className="text-[var(--foreground)]">{formatCost(school.estimated_annual_cost)}</strong></span>
                          )}
                          {school.academic_fit && (
                            <span className="text-[var(--muted)]">Academic fit: <strong className="text-[var(--foreground)]">{school.academic_fit.charAt(0).toUpperCase() + school.academic_fit.slice(1)}</strong></span>
                          )}
                          {school.niche_academic_grade && (
                            <span className="text-[var(--muted)]">Niche grade: <strong className="text-[var(--foreground)]">{school.niche_academic_grade}</strong></span>
                          )}
                        </div>

                        {(school.research_confidence || school.opportunity_fit || school.ranking_adjustment != null) && (
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                            {school.research_confidence && (
                              <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                                <p className="text-xs text-[var(--muted)]">Research confidence</p>
                                <p className="mt-0.5 text-sm font-semibold text-[var(--foreground)]">
                                  {school.research_confidence}
                                </p>
                              </div>
                            )}
                            {school.opportunity_fit && (
                              <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                                <p className="text-xs text-[var(--muted)]">Roster opportunity</p>
                                <p className="mt-0.5 text-sm font-semibold text-[var(--foreground)]">
                                  {school.opportunity_fit}
                                </p>
                              </div>
                            )}
                            {school.ranking_adjustment != null && (
                              <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                                <p className="text-xs text-[var(--muted)]">Ranking adjustment</p>
                                <p className="mt-0.5 text-sm font-semibold text-[var(--foreground)]">
                                  {school.ranking_adjustment > 0 ? "+" : ""}
                                  {school.ranking_adjustment.toFixed(1)}
                                </p>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Fit summary (LLM-generated) */}
                        {school.fit_summary && (
                          <p className="text-sm text-[var(--foreground)] leading-relaxed">
                            {school.fit_summary}
                          </p>
                        )}

                        {school.roster_summary && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Roster outlook</p>
                            <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                              {school.roster_summary}
                            </p>
                          </div>
                        )}

                        {school.opportunity_summary && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Opportunity context</p>
                            <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                              {school.opportunity_summary}
                            </p>
                          </div>
                        )}

                        {school.school_description && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">About this program</p>
                            <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                              {school.school_description}
                            </p>
                          </div>
                        )}

                        {school.trend_summary && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Program trend</p>
                            <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                              {school.trend_summary}
                            </p>
                          </div>
                        )}

                        {(school.research_reasons?.length || school.research_risks?.length || school.research_data_gaps?.length) && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Research notes</p>
                            {school.research_reasons?.length ? (
                              <div className="mt-2">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Positives</p>
                                <ul className="mt-1 space-y-1 text-sm text-[var(--foreground)]">
                                  {school.research_reasons.map((reason) => (
                                    <li key={reason}>- {reason}</li>
                                  ))}
                                </ul>
                              </div>
                            ) : null}
                            {school.research_risks?.length ? (
                              <div className="mt-3">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Risks</p>
                                <ul className="mt-1 space-y-1 text-sm text-[var(--foreground)]">
                                  {school.research_risks.map((risk) => (
                                    <li key={risk}>- {risk}</li>
                                  ))}
                                </ul>
                              </div>
                            ) : null}
                            {school.research_data_gaps?.length ? (
                              <div className="mt-3">
                                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Data gaps</p>
                                <ul className="mt-1 space-y-1 text-sm text-[var(--foreground)]">
                                  {school.research_data_gaps.map((gap) => (
                                    <li key={gap}>- {gap}</li>
                                  ))}
                                </ul>
                              </div>
                            ) : null}
                          </div>
                        )}

                        {school.research_sources?.length ? (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Research sources</p>
                            <ul className="mt-2 space-y-1 text-sm">
                              {school.research_sources.map((source) => (
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
                        ) : null}

                        {/* Metric comparisons */}
                        {school.metric_comparisons && school.metric_comparisons.length > 0 && (
                          <div className="overflow-hidden rounded-xl border border-[var(--stroke)]">
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
                                {school.metric_comparisons.map((m) => {
                                  const diff = m.player_value - m.division_avg;
                                  const isPositive = diff > 0;
                                  const isTimeBased = m.unit === "sec";
                                  const isGood = isTimeBased ? diff < 0 : diff > 0;
                                  return (
                                    <tr key={m.metric} className="border-t border-[var(--stroke)]/50">
                                      <td className="px-3 py-1.5 font-medium text-[var(--foreground)]">{m.metric}</td>
                                      <td className="px-3 py-1.5 text-right font-semibold text-[var(--foreground)]">
                                        {m.player_value} {m.unit}
                                      </td>
                                      <td className="px-3 py-1.5 text-right text-[var(--muted)]">
                                        {m.division_avg} {m.unit}
                                      </td>
                                      <td
                                        className="px-3 py-1.5 text-right font-semibold"
                                        style={{ color: isGood ? "var(--sage-green)" : "var(--copper)" }}
                                      >
                                        {isPositive ? "+" : ""}{diff.toFixed(1)}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          </>}

          {/* Bottom create account CTA */}
          <div className="mt-10 rounded-2xl border-2 border-[var(--primary)]/30 bg-[var(--primary)]/5 p-6 text-center">
            <p className="display-font text-xl">Save your results</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Create a free account to access these results anytime and get your next evaluation for just $29.
            </p>
            <a
              href={`/signup?next=${encodeURIComponent(`/predict/claim-results?session_token=${sessionToken}&purchase_id=${purchaseId}&run_id=${results?.run_id}`)}`}
              className="mt-4 inline-block rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold !text-white"
            >
              Create Free Account
            </a>
          </div>
        </div>
      </main>
    </div>
  );
}
