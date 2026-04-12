"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { ResultsMap } from "@/components/evaluation/results-map";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SchoolLocation = {
  state?: string;
  region?: string;
  latitude?: number;
  longitude?: number;
};

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
  location?: SchoolLocation;
  baseball_fit?: string;
  fit_label?: string;
  delta?: number;
  sci?: number;
  trend?: string;
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
  review_adjustment_from_base?: string;
  ranking_adjustment?: number;
  ranking_score?: number;
  research_status?: string;
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

type EvaluationRun = {
  id: string;
  created_at?: string;
  position_track?: string;
  identity_input?: Record<string, unknown>;
  stats_input?: Record<string, unknown>;
  preferences_input?: Record<string, unknown>;
  prediction_response?: Record<string, unknown>;
  preferences_response?: {
    schools?: School[];
    academic_score?: AcademicScore;
    baseball_assessment?: BaseballAssessment;
  };
  llm_reasoning_status?: string;
};

type SavedSchoolRecord = {
  id: string;
  school_name?: string;
  school_logo_image?: string | null;
  dedupe_key?: string;
  school_data?: School;
  note?: string | null;
  created_at?: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FIT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  fit: { bg: "rgba(107,143,94,0.15)", text: "var(--sage-green)", border: "var(--sage-green)" },
  reach: { bg: "rgba(184,115,51,0.15)", text: "var(--copper)", border: "var(--copper)" },
  safety: { bg: "rgba(212,168,67,0.15)", text: "var(--golden-sand)", border: "var(--golden-sand)" },
};

const MEDAL_COLORS = ["#D4A843", "#C0C0C0", "#CD7F32"];

const DISCLAIMER_TEXT =
  "This evaluation is based on measurable athletic metrics and academic data only. " +
  "Factors that college coaches weigh heavily \u2014 including coachability, work ethic, " +
  "character, delivery style, baseball IQ, development trajectory, and roster context " +
  "\u2014 are not captured in this snapshot. Players with unique profiles (sidearm deliveries, " +
  "exceptional competitiveness, late physical development) may be undervalued or " +
  "overvalued by any metrics-based tool. This is a starting point for your college " +
  "baseball search, not the final word.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getNcaLogoUrl(logoKey: string | null | undefined): string | null {
  const key = (logoKey || "").trim();
  if (!key) return null;
  return `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(key)}.svg`;
}

function getSchoolDedupeKey(school: School): string {
  const logoKey = (school.school_logo_image || "").trim().toLowerCase();
  if (logoKey) return `logo:${logoKey}`;
  return `name:${school.school_name.trim().toLowerCase()}`;
}

function formatCost(cost: number | null | undefined): string {
  if (cost == null) return "N/A";
  return `$${cost.toLocaleString()}/yr`;
}

function formatPercentile(pct: number | undefined): string {
  if (pct == null) return "N/A";
  return `${pct.toFixed(0)}th percentile`;
}

function formatProbability(prob: number | undefined): string {
  if (prob == null) return "N/A";
  return `${(prob * 100).toFixed(0)}%`;
}

function tierDisplayLabel(tier: string | undefined): string {
  if (!tier) return "Unknown";
  if (tier.includes("Power 4")) return "Power 4";
  if (tier.includes("Non-P4")) return "Division 1";
  if (tier.includes("Non-D1")) return "Non-D1";
  return tier;
}

function fitLabel(fit: string | undefined): string {
  if (!fit) return "";
  return fit
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function fitColorKey(fit: string | undefined): string {
  const lower = (fit || "").toLowerCase();
  if (lower.includes("safety")) return "safety";
  if (lower.includes("reach")) return "reach";
  return "fit";
}

function schoolDivisionLabel(school: School): string {
  if (school.division_label) return school.division_label;
  if (school.division_group?.includes("Power 4")) return "Power 4";
  if (school.division_group?.includes("Non-P4")) return "Division 1";
  if (school.baseball_division === 2) return "Division 2";
  if (school.baseball_division === 3) return "Division 3";
  return "";
}

function baseballFitText(school: School): string {
  if (school.fit_label) return school.fit_label;
  return fitLabel(school.baseball_fit);
}

function schoolDisplayName(school: School): string {
  return school.display_school_name || school.school_name;
}

function isV2Evaluation(run: EvaluationRun): boolean {
  return Boolean(run.preferences_response?.baseball_assessment);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FitBadge({ type, label }: { type: string; label: string }) {
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

function DisclaimerBanner() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className="rounded-2xl border p-4"
      style={{
        background: "rgba(212,168,67,0.08)",
        borderColor: "rgba(212,168,67,0.25)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 text-lg" style={{ color: "var(--golden-sand)" }}>
            &#9888;
          </span>
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--walnut)" }}>
              Important disclaimer
            </p>
            {!collapsed && (
              <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
                {DISCLAIMER_TEXT}
              </p>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="shrink-0 text-xs font-semibold"
          style={{ color: "var(--primary)" }}
        >
          {collapsed ? "Show" : "Hide"}
        </button>
      </div>
    </div>
  );
}

function MetricComparisonTable({ comparisons }: { comparisons: MetricComparison[] }) {
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
            // For time-based metrics (sec), lower is better
            const isTimeBased = m.unit === "sec";
            const isGood = isTimeBased ? diff < 0 : diff > 0;

            return (
              <tr key={m.metric} className="border-t border-[var(--stroke)]/50">
                <td className="px-3 py-1.5 font-medium text-[var(--foreground)]">{m.metric}</td>
                <td className="px-3 py-1.5 text-right font-semibold text-[var(--navy)]">
                  {m.player_value} {m.unit}
                </td>
                <td className="px-3 py-1.5 text-right text-[var(--muted)]">
                  {m.division_avg} {m.unit}
                </td>
                <td
                  className="px-3 py-1.5 text-right font-semibold"
                  style={{ color: isGood ? "var(--sage-green)" : "var(--copper)" }}
                >
                  {isPositive ? "+" : ""}
                  {diff.toFixed(1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function EvaluationDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const { loading: authLoading, accessToken, user } = useRequireAuth(`/evaluations/${runId}`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);
  const [selectedSchoolKey, setSelectedSchoolKey] = useState<string | null>(null);
  const [savedSchoolByKey, setSavedSchoolByKey] = useState<Record<string, SavedSchoolRecord>>({});
  const [saveSchoolNote, setSaveSchoolNote] = useState("");
  const [savingSchool, setSavingSchool] = useState(false);
  const [saveSchoolMessage, setSaveSchoolMessage] = useState("");
  const [deletingRun, setDeletingRun] = useState(false);
  const detailRef = useRef<HTMLDivElement>(null);

  // Load evaluation
  useEffect(() => {
    if (!accessToken || !runId) return;
    let mounted = true;

    async function loadEvaluation() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/evaluations/${runId}`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.detail || "Failed to load evaluation.");
        }
        if (!mounted) return;
        setEvaluation(data as EvaluationRun);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load evaluation.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadEvaluation();
    return () => { mounted = false; };
  }, [accessToken, runId]);

  useEffect(() => {
    if (!accessToken || !runId || evaluation?.llm_reasoning_status !== "processing") return;

    let cancelled = false;
    const intervalId = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/evaluations/${runId}`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        if (!response.ok || cancelled) return;
        const data = await response.json();
        if (cancelled) return;
        setEvaluation(data as EvaluationRun);
        if ((data as EvaluationRun).llm_reasoning_status !== "processing") {
          window.clearInterval(intervalId);
        }
      } catch {
        // Keep polling while the background job is running.
      }
    }, 8000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [accessToken, runId, evaluation?.llm_reasoning_status]);

  // Load saved schools
  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadSavedSchools() {
      try {
        const response = await fetch(`${API_BASE_URL}/saved-schools`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        if (!response.ok) return;
        const data = await response.json();
        if (!mounted) return;
        const nextMap: Record<string, SavedSchoolRecord> = {};
        for (const item of data.items || []) {
          if (item.dedupe_key) nextMap[item.dedupe_key] = item;
        }
        setSavedSchoolByKey(nextMap);
      } catch { /* ignore */ }
    }

    loadSavedSchools();
    return () => { mounted = false; };
  }, [accessToken]);

  // Derived data
  const schools = useMemo(
    () => evaluation?.preferences_response?.schools || [],
    [evaluation?.preferences_response?.schools],
  );

  const baseball = evaluation?.preferences_response?.baseball_assessment;
  const academic = evaluation?.preferences_response?.academic_score;
  const llmStatus = evaluation?.llm_reasoning_status;
  const v2 = evaluation ? isV2Evaluation(evaluation) : false;

  const selectedSchool = useMemo(() => {
    if (schools.length === 0) return null;
    if (!selectedSchoolKey) return schools[0];
    return schools.find((s) => getSchoolDedupeKey(s) === selectedSchoolKey) || schools[0];
  }, [selectedSchoolKey, schools]);

  const selectedRank = selectedSchool?.rank ?? null;

  const selectedDedupeKey = useMemo(
    () => (selectedSchool ? getSchoolDedupeKey(selectedSchool) : null),
    [selectedSchool],
  );
  const isSelectedSaved = selectedDedupeKey ? Boolean(savedSchoolByKey[selectedDedupeKey]) : false;

  // Reset note when selected school changes
  useEffect(() => {
    if (!selectedSchool) {
      setSaveSchoolNote("");
      setSaveSchoolMessage("");
      return;
    }
    const saved = selectedDedupeKey ? savedSchoolByKey[selectedDedupeKey] : undefined;
    setSaveSchoolNote(saved?.note || "");
    setSaveSchoolMessage("");
  }, [selectedSchool, selectedDedupeKey, savedSchoolByKey]);

  // Select school handler
  function selectSchool(rank: number) {
    const school = schools.find((candidate) => candidate.rank === rank);
    if (school) {
      setSelectedSchoolKey(getSchoolDedupeKey(school));
    }
    // Scroll detail panel into view on mobile
    if (window.innerWidth < 1024) {
      setTimeout(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    }
  }

  // Save school
  async function saveSelectedSchool() {
    if (!accessToken || !selectedSchool || isSelectedSaved || savingSchool) return;
    setSavingSchool(true);
    setSaveSchoolMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/saved-schools`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          school_name: selectedSchool.school_name,
          school_logo_image: selectedSchool.school_logo_image || null,
          school_data: selectedSchool,
          note: saveSchoolNote.trim() || null,
          evaluation_run_id: runId,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        if (response.status === 409) {
          setSaveSchoolMessage("School already saved.");
          return;
        }
        throw new Error(payload.detail || "Failed to save school.");
      }

      const dedupeKey = payload.dedupe_key || selectedDedupeKey || getSchoolDedupeKey(selectedSchool);
      setSavedSchoolByKey((curr) => ({ ...curr, [dedupeKey]: payload }));
      setSaveSchoolMessage("School saved!");
    } catch (e) {
      setSaveSchoolMessage(e instanceof Error ? e.message : "Failed to save school.");
    } finally {
      setSavingSchool(false);
    }
  }

  // Delete run
  async function deleteCurrentRun() {
    if (!accessToken || deletingRun) return;
    const confirmed = window.confirm("Delete this evaluation run?");
    if (!confirmed) return;

    setDeletingRun(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/evaluations/${runId}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Failed to delete.");
      router.push("/evaluations");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete evaluation run.");
    } finally {
      setDeletingRun(false);
    }
  }

  // Page metadata
  const playerName = (evaluation?.identity_input?.name as string) || "Evaluation";
  const positionLabel = (evaluation?.identity_input?.primary_position as string) ||
    (evaluation?.stats_input?.primary_position as string) || "";
  const reportDate = evaluation?.created_at
    ? new Date(evaluation.created_at).toLocaleDateString()
    : "";

  // Loading state
  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading evaluation report...</p>
        </div>
      </div>
    );
  }

  if (error && !evaluation) {
    return (
      <div className="min-h-screen">
        {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}
        <div className="mx-auto max-w-3xl px-6 pt-12">
          <div className="rounded-2xl border border-red-300 bg-red-50 p-6 text-center text-sm text-red-700">
            {error}
          </div>
          <div className="mt-4 text-center">
            <Link href="/evaluations" className="text-sm font-semibold text-[var(--primary)] hover:underline">
              Back to evaluations
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-4 pt-5 pb-12 md:px-6 md:pt-6">
        <div className="mx-auto max-w-6xl">
          {/* Header */}
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="display-font text-3xl md:text-4xl">
                {playerName}&apos;s Evaluation
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-[var(--muted)]">
                {positionLabel && (
                  <span className="rounded-full bg-[var(--sand)] px-3 py-0.5 text-xs font-semibold text-[var(--navy)]">
                    {positionLabel}
                  </span>
                )}
                {reportDate && <span>{reportDate}</span>}
                {v2 && baseball?.predicted_tier && (
                  <span className="font-semibold text-[var(--navy)]">
                    {tierDisplayLabel(baseball.predicted_tier)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                href="/predict"
                className="rounded-full bg-[var(--primary)] px-5 py-2 text-sm font-semibold !text-white shadow-soft"
              >
                New evaluation
              </Link>
              <Link
                href="/evaluations"
                className="rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2 text-sm font-semibold text-[var(--navy)]"
              >
                All evaluations
              </Link>
              <button
                type="button"
                onClick={deleteCurrentRun}
                disabled={deletingRun}
                className="rounded-full border border-red-300 bg-white px-5 py-2 text-sm font-semibold text-red-700 disabled:opacity-50"
              >
                {deletingRun ? "Removing..." : "Remove"}
              </button>
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          )}

          {/* Disclaimer */}
          {v2 && (
            <div className="mt-5">
              <DisclaimerBanner />
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
            <div className="mt-5 rounded-2xl border border-red-300 bg-red-50 p-4">
              <p className="text-sm font-semibold text-red-700">
                Deep roster research did not complete.
              </p>
              <p className="mt-1 text-xs text-red-700">
                The current report still reflects the base athletic and academic match.
              </p>
            </div>
          )}

          {/* Assessment Summary Cards — hidden while research is running */}
          {llmStatus !== "processing" && v2 && (baseball || academic) && (
            <section className="mt-6 grid gap-4 md:grid-cols-2">
              {/* Baseball Assessment */}
              {baseball && (
                <div className="glass rounded-2xl p-5 shadow-soft">
                  <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Baseball assessment</p>
                  <p className="mt-3 text-2xl font-bold text-[var(--foreground)]">
                    {tierDisplayLabel(baseball.predicted_tier)}
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-xs text-[var(--muted)]">Within-tier</p>
                      <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                        {formatPercentile(baseball.within_tier_percentile)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-xs text-[var(--muted)]">D1 probability</p>
                      <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                        {formatProbability(baseball.d1_probability)}
                      </p>
                    </div>
                    {baseball.p4_probability != null && (
                      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <p className="text-xs text-[var(--muted)]">P4 probability</p>
                        <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                          {formatProbability(baseball.p4_probability)}
                        </p>
                      </div>
                    )}
                    {baseball.confidence && (
                      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <p className="text-xs text-[var(--muted)]">Confidence</p>
                        <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                          {baseball.confidence}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Academic Assessment */}
              {academic && (
                <div className="glass rounded-2xl p-5 shadow-soft">
                  <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Academic assessment</p>
                  <p className="mt-3 text-2xl font-bold text-[var(--foreground)]">
                    {academic.composite != null ? `${academic.composite.toFixed(1)} / 10` : "N/A"}
                  </p>
                  <div className="mt-3 grid grid-cols-3 gap-3">
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-xs text-[var(--muted)]">GPA</p>
                      <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                        {academic.gpa_rating != null ? academic.gpa_rating.toFixed(1) : "N/A"}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-xs text-[var(--muted)]">Test score</p>
                      <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                        {academic.test_rating != null ? academic.test_rating.toFixed(1) : "N/A"}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                      <p className="text-xs text-[var(--muted)]">AP courses</p>
                      <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                        {academic.ap_rating != null ? academic.ap_rating.toFixed(1) : "N/A"}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Map — hidden while research is running */}
          {llmStatus !== "processing" && v2 && schools.length > 0 && (
            <section className="mt-6">
              <ResultsMap
                schools={schools.map((s) => ({
                  rank: s.rank,
                  school_name: schoolDisplayName(s),
                  state: s.location?.state || "",
                }))}
                selectedRank={selectedRank ?? (schools[0]?.rank || null)}
                onSelect={selectSchool}
                highlightedRegions={(evaluation?.preferences_input?.regions as string[] | undefined) || null}
              />
            </section>
          )}

          {/* Schools section — hidden while research is running */}
          {llmStatus !== "processing" && <section className="mt-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">
                  Matched schools ({schools.length})
                </p>
                {v2 && (
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Click a school to view detailed fit analysis
                  </p>
                )}
              </div>
            </div>

            {schools.length === 0 ? (
              <div className="rounded-2xl border border-[var(--stroke)] bg-white/75 p-8 text-center">
                <p className="text-sm font-semibold text-[var(--foreground)]">No schools matched your criteria.</p>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Try broadening your region or budget preferences.
                </p>
              </div>
            ) : (
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
                {/* School list */}
                <div className="space-y-3">
                  {schools.map((school) => {
                    const isActive = (selectedDedupeKey ?? getSchoolDedupeKey(schools[0])) === getSchoolDedupeKey(school);
                    const logoUrl = getNcaLogoUrl(school.school_logo_image);
                    const medalIdx = school.rank - 1;
                    const hasMedal = medalIdx < 3;
                    const schoolTierLabel = schoolDivisionLabel(school);

                    return (
                      <button
                        key={getSchoolDedupeKey(school)}
                        type="button"
                        onClick={() => selectSchool(school.rank)}
                        className={`w-full rounded-2xl border bg-white/80 p-4 text-left shadow-soft transition-all duration-200 ${
                          isActive
                            ? "border-[var(--primary)] ring-1 ring-[var(--primary)]"
                            : "border-[var(--stroke)] hover:-translate-y-0.5 hover:border-[var(--primary)]/40"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              {hasMedal && (
                                <span
                                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                                  style={{ background: MEDAL_COLORS[medalIdx] }}
                                >
                                  {school.rank}
                                </span>
                              )}
                              {!hasMedal && (
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--sand)] text-xs font-semibold text-[var(--navy)]">
                                  {school.rank}
                                </span>
                              )}
                              <p className="text-sm font-semibold text-[var(--foreground)] md:text-base">
                                {schoolDisplayName(school)}
                              </p>
                            </div>

                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              {schoolTierLabel && (
                                <span className="rounded-full bg-[var(--sand)] px-2.5 py-0.5 text-xs font-semibold text-[var(--navy)]">
                                  {schoolTierLabel}
                                </span>
                              )}
                              {school.conference && (
                                <span className="text-xs text-[var(--muted)]">{school.conference}</span>
                              )}
                              {school.location?.state && (
                                <span className="text-xs text-[var(--muted)]">{school.location.state}</span>
                              )}
                            </div>

                            {v2 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {school.baseball_fit && (
                                  <FitBadge
                                    type={school.fit_label || school.baseball_fit}
                                    label={`Baseball: ${baseballFitText(school)}`}
                                  />
                                )}
                                {school.academic_fit && (
                                  <FitBadge
                                    type={school.academic_fit}
                                    label={`Academic: ${fitLabel(school.academic_fit)}`}
                                  />
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
                            )}
                          </div>

                          {logoUrl && (
                            <img
                              src={logoUrl}
                              alt=""
                              loading="lazy"
                              onError={(e) => { e.currentTarget.style.display = "none"; }}
                              className="h-12 w-12 shrink-0 rounded-lg border border-[var(--stroke)] bg-white/90 p-1.5 object-contain"
                            />
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Detail panel */}
                <aside
                  ref={detailRef}
                  className="glass rounded-2xl p-5 shadow-soft lg:sticky lg:top-24 lg:max-h-[82vh] lg:overflow-y-auto"
                >
                  {selectedSchool ? (
                    <div key={selectedDedupeKey} className="detail-slide-in">
                      {/* Header */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            {selectedSchool.rank <= 3 && (
                              <span
                                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                                style={{ background: MEDAL_COLORS[selectedSchool.rank - 1] }}
                              >
                                {selectedSchool.rank}
                              </span>
                            )}
                            <h2 className="text-lg font-bold text-[var(--foreground)]">
                              {schoolDisplayName(selectedSchool)}
                            </h2>
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
                            {selectedSchool.conference && <span>{selectedSchool.conference}</span>}
                            {selectedSchool.conference && selectedSchool.location?.state && <span>&middot;</span>}
                            {selectedSchool.location?.state && <span>{selectedSchool.location.state}</span>}
                            {selectedSchool.location?.region && (
                              <>
                                <span>&middot;</span>
                                <span>{selectedSchool.location.region}</span>
                              </>
                            )}
                          </div>
                        </div>
                        {getNcaLogoUrl(selectedSchool.school_logo_image) && (
                          <img
                            src={getNcaLogoUrl(selectedSchool.school_logo_image)!}
                            alt=""
                            onError={(e) => { e.currentTarget.style.display = "none"; }}
                            className="h-14 w-14 shrink-0 rounded-lg border border-[var(--stroke)] bg-white/90 p-1.5 object-contain"
                          />
                        )}
                      </div>

                      {/* Fit labels + tier + cost */}
                      <div className="mt-4 flex flex-wrap gap-2">
                        {schoolDivisionLabel(selectedSchool) && (
                          <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                            {schoolDivisionLabel(selectedSchool)}
                          </span>
                        )}
                        {selectedSchool.baseball_fit && (
                          <FitBadge
                            type={selectedSchool.fit_label || selectedSchool.baseball_fit}
                            label={`Baseball: ${baseballFitText(selectedSchool)}`}
                          />
                        )}
                        {selectedSchool.academic_fit && (
                          <FitBadge
                            type={selectedSchool.academic_fit}
                            label={`Academic: ${fitLabel(selectedSchool.academic_fit)}`}
                          />
                        )}
                        {selectedSchool.roster_label && selectedSchool.roster_label !== "unknown" && (
                          <span
                            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                            style={{
                              background: selectedSchool.roster_label === "open" ? "#dcfce7" : selectedSchool.roster_label === "crowded" ? "#fef3c7" : "#f3f4f6",
                              color: selectedSchool.roster_label === "open" ? "#166534" : selectedSchool.roster_label === "crowded" ? "#92400e" : "#374151",
                              border: `1px solid ${selectedSchool.roster_label === "open" ? "#86efac" : selectedSchool.roster_label === "crowded" ? "#fcd34d" : "#d1d5db"}`,
                            }}
                          >
                            {selectedSchool.roster_label === "open" ? "Open" : selectedSchool.roster_label === "crowded" ? "Crowded" : "Competitive"}
                          </span>
                        )}
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-3">
                        {selectedSchool.niche_academic_grade && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                            <p className="text-xs text-[var(--muted)]">Niche academic grade</p>
                            <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                              {selectedSchool.niche_academic_grade}
                            </p>
                          </div>
                        )}
                        <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                          <p className="text-xs text-[var(--muted)]">Est. annual cost</p>
                          <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                            {formatCost(selectedSchool.estimated_annual_cost)}
                          </p>
                        </div>
                      </div>

                      {(selectedSchool.research_confidence || selectedSchool.opportunity_fit || selectedSchool.ranking_adjustment != null) && (
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                          {selectedSchool.research_confidence && (
                            <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                              <p className="text-xs text-[var(--muted)]">Research confidence</p>
                              <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                                {selectedSchool.research_confidence}
                              </p>
                            </div>
                          )}
                          {selectedSchool.opportunity_fit && (
                            <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                              <p className="text-xs text-[var(--muted)]">Roster opportunity</p>
                              <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                                {selectedSchool.opportunity_fit}
                              </p>
                            </div>
                          )}
                          {selectedSchool.ranking_adjustment != null && (
                            <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                              <p className="text-xs text-[var(--muted)]">Ranking adjustment</p>
                              <p className="mt-0.5 text-sm font-semibold text-[var(--navy)]">
                                {selectedSchool.ranking_adjustment > 0 ? "+" : ""}
                                {selectedSchool.ranking_adjustment.toFixed(1)}
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* LLM Fit Summary */}
                      {selectedSchool.fit_summary && (
                        <div className="mt-4 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Fit analysis</p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                            {selectedSchool.fit_summary}
                          </p>
                        </div>
                      )}

                      {selectedSchool.roster_summary && (
                        <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Roster outlook</p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                            {selectedSchool.roster_summary}
                          </p>
                        </div>
                      )}

                      {selectedSchool.opportunity_summary && (
                        <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Opportunity context</p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                            {selectedSchool.opportunity_summary}
                          </p>
                        </div>
                      )}

                      {/* LLM School Description */}
                      {selectedSchool.school_description && (
                        <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">About this program</p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                            {selectedSchool.school_description}
                          </p>
                        </div>
                      )}

                      {selectedSchool.trend_summary && (
                        <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Program trend</p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                            {selectedSchool.trend_summary}
                          </p>
                        </div>
                      )}

                      {(selectedSchool.research_reasons?.length || selectedSchool.research_risks?.length || selectedSchool.research_data_gaps?.length) && (
                        <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Research notes</p>
                          {selectedSchool.research_reasons?.length ? (
                            <div className="mt-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Positives</p>
                              <ul className="mt-1 space-y-1 text-sm text-[var(--foreground)]">
                                {selectedSchool.research_reasons.map((reason) => (
                                  <li key={reason}>- {reason}</li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {selectedSchool.research_risks?.length ? (
                            <div className="mt-3">
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Risks</p>
                              <ul className="mt-1 space-y-1 text-sm text-[var(--foreground)]">
                                {selectedSchool.research_risks.map((risk) => (
                                  <li key={risk}>- {risk}</li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {selectedSchool.research_data_gaps?.length ? (
                            <div className="mt-3">
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Data gaps</p>
                              <ul className="mt-1 space-y-1 text-sm text-[var(--foreground)]">
                                {selectedSchool.research_data_gaps.map((gap) => (
                                  <li key={gap}>- {gap}</li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      )}

                      {selectedSchool.research_sources?.length ? (
                        <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Research sources</p>
                          <ul className="mt-2 space-y-1 text-sm">
                            {selectedSchool.research_sources.map((source) => (
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
                      {selectedSchool.metric_comparisons && selectedSchool.metric_comparisons.length > 0 && (
                        <div className="mt-4">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                            Your metrics vs. {schoolDivisionLabel(selectedSchool) || "division"} average
                          </p>
                          <MetricComparisonTable comparisons={selectedSchool.metric_comparisons} />
                        </div>
                      )}

                      {/* Save school */}
                      <div className="mt-4 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                        <div className="flex items-center justify-between">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Save school</p>
                          {isSelectedSaved && (
                            <span className="rounded-full bg-[var(--sage-green)] px-2 py-0.5 text-xs font-semibold text-white">
                              Saved
                            </span>
                          )}
                        </div>
                        <textarea
                          value={saveSchoolNote}
                          onChange={(e) => setSaveSchoolNote(e.target.value)}
                          placeholder="Notes about this school..."
                          className="form-control mt-3 min-h-[72px] resize-y text-sm"
                        />
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                          <button
                            type="button"
                            onClick={saveSelectedSchool}
                            disabled={isSelectedSaved || savingSchool}
                            className="rounded-full bg-[var(--primary)] px-4 py-2 text-xs font-semibold !text-white shadow-soft disabled:opacity-50"
                          >
                            {isSelectedSaved ? "Saved" : savingSchool ? "Saving..." : "Save School"}
                          </button>
                          <Link
                            href="/saved-schools"
                            className="text-xs font-semibold text-[var(--primary)] hover:underline"
                          >
                            View saved
                          </Link>
                        </div>
                        {saveSchoolMessage && (
                          <p className="mt-2 text-xs text-[var(--muted)]">{saveSchoolMessage}</p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-6 text-center">
                      <p className="text-sm text-[var(--muted)]">Select a school to view details.</p>
                    </div>
                  )}
                </aside>
              </div>
            )}
          </section>}
        </div>
      </main>

      <style jsx>{`
        .detail-slide-in {
          animation: detailSlideIn 220ms ease;
        }
        @keyframes detailSlideIn {
          from {
            opacity: 0;
            transform: translateX(12px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
