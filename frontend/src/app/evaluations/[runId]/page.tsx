"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Info } from "lucide-react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { ResultsMap } from "@/components/evaluation/results-map";
import { SchoolFitVote, type SchoolFeedbackRecord } from "@/components/evaluation/school-fit-vote";
import { ReviewHelpfulnessVote, type ReviewFeedbackRecord } from "@/components/evaluation/review-helpfulness-vote";
import { EvalFeedbackPanel } from "@/components/evaluation/eval-feedback-panel";
import {
  MetricComparisonsSection,
  ResearchSourcesCard,
  type School,
  SchoolFitBadges,
  SchoolHeader,
  SchoolListCard,
  SchoolStatsGrid,
  WhyThisSchoolCard,
  getSchoolDedupeKey,
  schoolDisplayName,
} from "@/components/evaluation/school-display";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

const DISCLAIMER_TEXT =
  "This evaluation is based on metrics and academics. Things coaches care about most like " +
  "coachability, work ethic, character, and development upside aren't in the model. " +
  "Use this as a starting point, not the final word.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function tierDisplayLabel(tier: string | undefined): string {
  if (!tier) return "Unknown";
  if (tier.includes("Power 4")) return "Power 4";
  if (tier.includes("Non-P4")) return "Division 1";
  if (tier.includes("Non-D1")) return "D2 & D3";
  return tier;
}

// Convert a within-tier percentile to coach-style language. A 71st-percentile
// player is in the top 29% of their tier — round to the nearest 5% so the
// number reads cleanly without leaking model precision.
function percentileInWords(pct: number | undefined, tierLabel: string): string | null {
  if (pct == null || !Number.isFinite(pct)) return null;
  const top = Math.max(5, Math.round((100 - pct) / 5) * 5);
  return `Top ${top}% of ${tierLabel} prospects`;
}

// Translate the 1-10 composite into a one-line coach-style interpretation
// instead of leaving the user to guess what 6.0/10 means.
function interpretAcademic(composite: number | undefined): string | null {
  if (composite == null || !Number.isFinite(composite)) return null;
  if (composite >= 9) return "Strong fit for highly selective academic programs.";
  if (composite >= 7) return "Strong fit for selective academic programs.";
  if (composite >= 5) return "Solid fit across a wide range of programs.";
  if (composite >= 3) return "Foundational profile — many programs available.";
  return "Best matched to programs prioritizing growth and broader admissions.";
}

// Render the tier label with the ampersand in the sans family — Fraunces
// (the display font) ships a swashy ampersand glyph at large sizes that
// reads as a typo. Sans gives a clean & for the same visual weight.
function renderTierLabel(tier: string | undefined): React.ReactNode {
  const label = tierDisplayLabel(tier);
  if (label === "D2 & D3") {
    return <>D2 <span className="font-sans">&amp;</span> D3</>;
  }
  return label;
}

// Pull the player's actual GPA, test, and AP count so we can show real numbers
// instead of the internal 0-10 ratings.
function getActualGpa(run: EvaluationRun): string | null {
  const acad = (run.preferences_input as Record<string, unknown> | undefined)?.academic_input;
  if (!acad || typeof acad !== "object") return null;
  const gpa = (acad as Record<string, unknown>).gpa;
  if (typeof gpa !== "number" || !Number.isFinite(gpa)) return null;
  return gpa.toFixed(2);
}

function getActualTestScore(run: EvaluationRun): { label: string; value: string } | null {
  const acad = (run.preferences_input as Record<string, unknown> | undefined)?.academic_input;
  if (!acad || typeof acad !== "object") return null;
  const obj = acad as Record<string, unknown>;
  const sat = typeof obj.sat_score === "number" && Number.isFinite(obj.sat_score) ? obj.sat_score : null;
  const act = typeof obj.act_score === "number" && Number.isFinite(obj.act_score) ? obj.act_score : null;
  if (sat) return { label: "SAT", value: String(sat) };
  if (act) return { label: "ACT", value: String(act) };
  return null;
}

function getActualApCourses(run: EvaluationRun): string | null {
  const acad = (run.preferences_input as Record<string, unknown> | undefined)?.academic_input;
  if (!acad || typeof acad !== "object") return null;
  const ap = (acad as Record<string, unknown>).ap_courses;
  if (typeof ap !== "number" || !Number.isFinite(ap)) return null;
  return String(Math.round(ap));
}

function isV2Evaluation(run: EvaluationRun): boolean {
  return Boolean(run.preferences_response?.baseball_assessment);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DisclaimerBanner() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface-2)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--cool-ink-muted)]" strokeWidth={2} />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--cool-ink)]">
              A note before you read.
            </p>
            {!collapsed && (
              <p className="mt-1 text-sm text-[var(--cool-ink-muted)] leading-relaxed">
                {DISCLAIMER_TEXT}
              </p>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="shrink-0 text-xs font-semibold text-[var(--cool-ink-muted)] hover:text-[var(--cool-ink)] transition-colors"
        >
          {collapsed ? "Show" : "Hide"}
        </button>
      </div>
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
  const [schoolFeedbackByKey, setSchoolFeedbackByKey] = useState<Record<string, SchoolFeedbackRecord>>({});
  const [reviewFeedbackByKey, setReviewFeedbackByKey] = useState<Record<string, ReviewFeedbackRecord>>({});
  const [showFeedbackPanel, setShowFeedbackPanel] = useState(false);
  const [feedbackEligible, setFeedbackEligible] = useState(false);
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

  // Load existing per-school feedback for this run
  useEffect(() => {
    if (!accessToken || !runId) return;
    let mounted = true;

    async function loadSchoolFeedback() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/feedback/school?evaluation_run_id=${encodeURIComponent(runId)}`,
          {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
          },
        );
        if (!response.ok) return;
        const data = await response.json();
        if (!mounted) return;
        const next: Record<string, SchoolFeedbackRecord> = {};
        for (const item of data.items || []) {
          if (item.school_dedupe_key) {
            next[item.school_dedupe_key] = {
              school_dedupe_key: item.school_dedupe_key,
              is_good_fit: item.is_good_fit,
              reason: item.reason ?? null,
            };
          }
        }
        setSchoolFeedbackByKey(next);
      } catch { /* ignore */ }
    }

    loadSchoolFeedback();
    return () => { mounted = false; };
  }, [accessToken, runId]);

  // Load existing per-school review-helpfulness feedback for this run
  useEffect(() => {
    if (!accessToken || !runId) return;
    let mounted = true;

    async function loadReviewFeedback() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/feedback/review?evaluation_run_id=${encodeURIComponent(runId)}`,
          {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
          },
        );
        if (!response.ok) return;
        const data = await response.json();
        if (!mounted) return;
        const next: Record<string, ReviewFeedbackRecord> = {};
        for (const item of data.items || []) {
          if (item.school_dedupe_key) {
            next[item.school_dedupe_key] = {
              school_dedupe_key: item.school_dedupe_key,
              is_helpful: item.is_helpful,
              reason: item.reason ?? null,
            };
          }
        }
        setReviewFeedbackByKey(next);
      } catch { /* ignore */ }
    }

    loadReviewFeedback();
    return () => { mounted = false; };
  }, [accessToken, runId]);

  // Check survey eligibility once results are ready
  useEffect(() => {
    if (!accessToken || !runId) return;
    if (evaluation?.llm_reasoning_status === "processing") return;
    let mounted = true;

    async function checkEligibility() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/feedback/run/eligibility?evaluation_run_id=${encodeURIComponent(runId)}`,
          {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
          },
        );
        if (!response.ok) return;
        const data = await response.json();
        if (!mounted) return;
        setFeedbackEligible(Boolean(data.eligible));
      } catch { /* ignore */ }
    }

    checkEligibility();
    return () => { mounted = false; };
  }, [accessToken, runId, evaluation?.llm_reasoning_status]);

  // 1-minute delay before revealing the inline feedback panel (skipped if
  // not eligible / dismissed this session).
  useEffect(() => {
    if (!feedbackEligible) return;
    if (evaluation?.llm_reasoning_status === "processing") return;
    if (typeof window === "undefined") return;
    const sessionDismissKey = `bp_eval_feedback_dismissed_${runId}`;
    if (sessionStorage.getItem(sessionDismissKey)) return;

    const timer = window.setTimeout(() => {
      setShowFeedbackPanel(true);
    }, 60000);
    return () => window.clearTimeout(timer);
  }, [feedbackEligible, evaluation?.llm_reasoning_status, runId]);

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
  function selectSchool(rank: number | undefined) {
    if (rank == null) return;
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
  // Last names get clunky in display headlines — first name reads more
  // naturally and is what a coach would say.
  const firstName = playerName.split(/\s+/).filter(Boolean)[0] || playerName;
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

      <main className="px-4 pt-10 pb-12 md:px-6 md:pt-14">
        <div className="mx-auto max-w-6xl">
          {/* Header — eyebrow above, then h1 + buttons in a center-aligned row
              so the buttons sit visually with the name (the dominant element)
              instead of with the small eyebrow. */}
          <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">
            Evaluation Report
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
            <h1 className="display-font text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight">
              {firstName}&apos;s Evaluation
            </h1>
            <div className="flex flex-wrap gap-2">
              <Link
                href="/predict"
                className="rounded-full bg-[var(--burnt-sienna)] px-5 py-2 text-sm font-semibold !text-white shadow-cool hover:-translate-y-0.5 transition-transform"
              >
                New evaluation
              </Link>
              <Link
                href="/evaluations"
                className="rounded-full border border-[var(--cool-stroke)] bg-white px-5 py-2 text-sm font-semibold text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors"
              >
                All evaluations
              </Link>
              <button
                type="button"
                onClick={deleteCurrentRun}
                disabled={deletingRun}
                className="rounded-full border border-red-200 bg-white px-5 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
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
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-[var(--cool-stroke)] border-t-[var(--burnt-sienna)]" />
              <p className="mt-5 text-base font-semibold text-[var(--cool-ink)]">
                Finding the best schools for you
              </p>
              <p className="mt-2 max-w-md text-center text-sm text-[var(--cool-ink-muted)] leading-relaxed">
                We&apos;re analyzing current rosters, academic standards, and positional need to surface schools where you actually fit. This takes about 90 seconds.
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
              {/* Baseball Assessment — coach-style, no raw probabilities */}
              {baseball && (() => {
                const tierLabel = tierDisplayLabel(baseball.predicted_tier);
                const percentileLine = percentileInWords(baseball.within_tier_percentile, tierLabel);
                return (
                  <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-6 shadow-cool">
                    <p className="text-[10px] uppercase tracking-[0.28em] text-[var(--cool-ink-muted)] font-semibold">
                      Baseball assessment
                    </p>
                    <p className="display-font mt-3 text-3xl font-semibold text-[var(--cool-ink)] tracking-tight">
                      {renderTierLabel(baseball.predicted_tier)}
                    </p>
                    {percentileLine && (
                      <p className="mt-3 text-sm font-medium text-[var(--cool-ink)]">
                        {percentileLine}
                      </p>
                    )}
                    <p className="mt-2 text-sm text-[var(--cool-ink-muted)] leading-relaxed">
                      See the school list below for the best fits for you.
                    </p>
                  </div>
                );
              })()}

              {/* Academic Assessment — keep composite, add interpretation,
                  show actual GPA/test instead of internal 0-10 ratings */}
              {academic && (() => {
                const interpretation = interpretAcademic(academic.composite);
                const actualGpa = getActualGpa(evaluation);
                const actualTest = getActualTestScore(evaluation);
                const actualAp = getActualApCourses(evaluation);
                const hasInputs = Boolean(actualGpa || actualTest || actualAp);
                return (
                  <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-6 shadow-cool">
                    <p className="text-[10px] uppercase tracking-[0.28em] text-[var(--cool-ink-muted)] font-semibold">
                      Academic assessment
                    </p>
                    <p className="display-font mt-3 text-3xl font-semibold text-[var(--cool-ink)] tracking-tight">
                      {academic.composite != null ? `${academic.composite.toFixed(1)} / 10` : "N/A"}
                    </p>
                    {interpretation && (
                      <p className="mt-3 text-sm font-medium text-[var(--cool-ink)]">
                        {interpretation}
                      </p>
                    )}
                    {hasInputs && (
                      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--cool-ink-muted)]">
                        {actualGpa && (
                          <span>
                            <span className="font-semibold text-[var(--cool-ink)]">GPA</span> {actualGpa}
                          </span>
                        )}
                        {actualTest && (
                          <span>
                            <span className="font-semibold text-[var(--cool-ink)]">{actualTest.label}</span> {actualTest.value}
                          </span>
                        )}
                        {actualAp && (
                          <span>
                            <span className="font-semibold text-[var(--cool-ink)]">AP courses</span> {actualAp}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}
            </section>
          )}

          {/* Map — hidden while research is running */}
          {llmStatus !== "processing" && v2 && schools.length > 0 && (
            <section className="mt-6">
              <ResultsMap
                schools={schools
                  .filter((s): s is School & { rank: number } => s.rank != null)
                  .map((s) => ({
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

          {/* Inline feedback panel — appears 60s after evaluation finalizes */}
          {showFeedbackPanel && accessToken && llmStatus !== "processing" && (
            <EvalFeedbackPanel
              accessToken={accessToken}
              evaluationRunId={runId}
              defaultName={(evaluation?.identity_input?.name as string) || null}
              onDismiss={() => {
                setShowFeedbackPanel(false);
                if (typeof window !== "undefined") {
                  sessionStorage.setItem(`bp_eval_feedback_dismissed_${runId}`, "1");
                }
              }}
            />
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
                    const isActive =
                      (selectedDedupeKey ?? getSchoolDedupeKey(schools[0])) === getSchoolDedupeKey(school);
                    return (
                      <SchoolListCard
                        key={getSchoolDedupeKey(school)}
                        school={school}
                        isActive={isActive}
                        onSelect={() => selectSchool(school.rank)}
                        showFitBadges={v2}
                      />
                    );
                  })}
                </div>

                {/* Detail panel */}
                <aside
                  ref={detailRef}
                  className="glass rounded-2xl p-5 shadow-soft lg:sticky lg:top-24 lg:max-h-[82vh] lg:overflow-y-auto"
                >
                  {selectedSchool ? (
                    <div key={selectedDedupeKey} className="detail-slide-in space-y-4">
                      <SchoolHeader school={selectedSchool} />
                      <SchoolFitBadges school={selectedSchool} />
                      <SchoolStatsGrid school={selectedSchool} />

                      {accessToken && selectedDedupeKey && (
                        <SchoolFitVote
                          accessToken={accessToken}
                          evaluationRunId={runId}
                          schoolDedupeKey={selectedDedupeKey}
                          schoolName={schoolDisplayName(selectedSchool)}
                          current={schoolFeedbackByKey[selectedDedupeKey] || null}
                          onSaved={(record) =>
                            setSchoolFeedbackByKey((prev) => ({
                              ...prev,
                              [record.school_dedupe_key]: record,
                            }))
                          }
                        />
                      )}

                      <WhyThisSchoolCard school={selectedSchool} />

                      {accessToken && selectedDedupeKey && (selectedSchool.why_this_school || selectedSchool.fit_summary) && (
                        <ReviewHelpfulnessVote
                          accessToken={accessToken}
                          evaluationRunId={runId}
                          schoolDedupeKey={selectedDedupeKey}
                          schoolName={schoolDisplayName(selectedSchool)}
                          current={reviewFeedbackByKey[selectedDedupeKey] || null}
                          onSaved={(record) =>
                            setReviewFeedbackByKey((prev) => ({
                              ...prev,
                              [record.school_dedupe_key]: record,
                            }))
                          }
                        />
                      )}

                      <ResearchSourcesCard sources={selectedSchool.research_sources} />
                      <MetricComparisonsSection school={selectedSchool} />

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

          {reportDate && (
            <p className="mt-12 text-center text-xs text-[var(--cool-ink-muted)]">
              Last updated {reportDate}
            </p>
          )}
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
