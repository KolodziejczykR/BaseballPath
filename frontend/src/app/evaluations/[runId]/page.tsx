"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type PreferencePoint = {
  preference?: string;
  description?: string;
};

type PreferenceMiss = {
  preference?: string;
  reason?: string;
};

type LLMReasoning = {
  summary?: string;
  fit_qualities?: string[];
  cautions?: string[];
};

type RelaxSuggestion = {
  preference?: string;
  suggestion?: string;
  reason?: string;
};

type SchoolResult = {
  school_name: string;
  division_group?: string;
  location?: {
    state?: string;
  };
  academics?: {
    grade?: string;
  };
  athletics?: {
    grade?: string;
  };
  match_analysis?: {
    total_nice_to_have_matches?: number;
    pros?: PreferencePoint[];
    cons?: PreferenceMiss[];
  };
  scores?: {
    playing_time_score?: number | null;
    nice_to_have_count?: number;
  };
  playing_time?: {
    available?: boolean;
    percentile?: number | null;
    bucket?: string | null;
    interpretation?: string | null;
    breakdown?: Record<string, number>;
    message?: string | null;
  };
  llm_reasoning?: LLMReasoning;
};

type RecommendationSummary = {
  llm_enabled?: boolean;
  llm_job_id?: string | null;
  llm_status?: string | null;
  player_summary?: string | null;
  relax_suggestions?: RelaxSuggestion[];
};

type EvaluationRun = {
  id: string;
  created_at?: string;
  identity_input?: Record<string, unknown>;
  stats_input?: Record<string, unknown>;
  preferences_input?: Record<string, unknown>;
  prediction_response?: {
    final_prediction?: string;
  };
  preferences_response?: {
    summary?: {
      total_matches?: number;
    };
    recommendation_summary?: RecommendationSummary;
    schools?: SchoolResult[];
  };
};

type ReasoningApiResponse = {
  success?: boolean;
  status?: string;
  reasoning?: Record<string, LLMReasoning> | null;
  player_summary?: string | null;
  relax_suggestions?: RelaxSuggestion[];
};

type SortMode = "default" | "playing_time" | "preferences";

const preferenceLabelMap: Record<string, string> = {
  preferred_regions: "Preferred regions",
  preferredRegion: "Preferred regions",
  preferred_school_size: "Preferred school size",
  preferredSchoolSize: "Preferred school size",
  min_academic_rating: "Minimum academic rating",
  minAcademicRating: "Minimum academic rating",
  min_athletics_rating: "Minimum athletics rating",
  minAthleticsRating: "Minimum athletics rating",
  party_scene_preference: "Party scene preference",
  partyScenePreference: "Party scene preference",
  max_budget: "Max yearly budget",
  maxBudget: "Max yearly budget",
};

function toDisplayValue(value: unknown): string {
  if (Array.isArray(value)) {
    const items = value.filter(Boolean).map((item) => String(item));
    return items.join(", ");
  }
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : "";
  return String(value).trim();
}

function getPlayerName(input: Record<string, unknown> | undefined): string {
  const name = toDisplayValue(input?.name);
  return name || "Saved Evaluation";
}

function getPositionLabel(
  input: Record<string, unknown> | undefined,
  statsInput: Record<string, unknown> | undefined,
): string {
  const identityPosition = toDisplayValue(input?.primary_position);
  if (identityPosition) return identityPosition;

  const statsPosition = toDisplayValue(statsInput?.primaryPosition);
  if (statsPosition) return statsPosition;

  return "Position unavailable";
}

function getPreferenceEntries(input: Record<string, unknown> | undefined): Array<{ label: string; value: string }> {
  if (!input) return [];

  const keys = Object.keys(preferenceLabelMap);
  const entries: Array<{ label: string; value: string }> = [];
  for (const key of keys) {
    const raw = input[key];
    const display = toDisplayValue(raw);
    if (!display) continue;
    entries.push({ label: preferenceLabelMap[key], value: display });
  }

  const unique = new Map<string, string>();
  for (const entry of entries) {
    if (!unique.has(entry.label)) {
      unique.set(entry.label, entry.value);
    }
  }

  return Array.from(unique.entries()).map(([label, value]) => ({ label, value }));
}

function getPreferenceSummary(entries: Array<{ label: string; value: string }>, maxItems = 3): string {
  if (entries.length === 0) return "No explicit preferences selected";
  return entries
    .slice(0, maxItems)
    .map((entry) => `${entry.label}: ${entry.value}`)
    .join(" · ");
}

function schoolIdentity(school: SchoolResult): string {
  return `${school.school_name}::${school.location?.state || ""}::${school.division_group || ""}`;
}

function hasReasoning(school: SchoolResult): boolean {
  const reasoning = school.llm_reasoning;
  return Boolean(
    reasoning &&
      (reasoning.summary || (reasoning.fit_qualities && reasoning.fit_qualities.length > 0) || (reasoning.cautions && reasoning.cautions.length > 0)),
  );
}

function findReasoningByName(
  reasoningMap: Record<string, LLMReasoning>,
  schoolName: string,
): LLMReasoning | undefined {
  if (reasoningMap[schoolName]) return reasoningMap[schoolName];

  const normalized = schoolName.trim().toLowerCase();
  for (const key of Object.keys(reasoningMap)) {
    if (key.trim().toLowerCase() === normalized) {
      return reasoningMap[key];
    }
  }

  return undefined;
}

function getPlayingTimePreview(school: SchoolResult): string {
  const playingTime = school.playing_time;
  if (playingTime?.available) {
    const bucket = playingTime.bucket || "Estimate available";
    if (typeof playingTime.percentile === "number") {
      return `${bucket} · ${playingTime.percentile.toFixed(1)} percentile`;
    }
    return bucket;
  }

  if (typeof school.scores?.playing_time_score === "number") {
    return `${school.scores.playing_time_score.toFixed(1)} score`;
  }

  return playingTime?.message || "Playing-time analysis unavailable";
}

export default function EvaluationDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { loading: authLoading, accessToken, user } = useRequireAuth(`/evaluations/${runId}`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("default");
  const [selectedSchoolId, setSelectedSchoolId] = useState<string | null>(null);
  const [llmPollingStatus, setLlmPollingStatus] = useState<string | null>(null);

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
        const data = (await response.json()) as EvaluationRun | { detail?: string };
        if (!response.ok) {
          throw new Error(
            typeof data === "object" && data && "detail" in data ? data.detail || "Failed to load evaluation." : "Failed to load evaluation.",
          );
        }
        if (!mounted) return;
        setEvaluation(data as EvaluationRun);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load evaluation.");
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    }

    loadEvaluation();
    return () => {
      mounted = false;
    };
  }, [accessToken, runId]);

  useEffect(() => {
    if (!accessToken || !evaluation) return;

    const summary = evaluation.preferences_response?.recommendation_summary;
    const llmJobId = summary?.llm_job_id;
    const schools = evaluation.preferences_response?.schools || [];
    const alreadyHasReasoning = schools.some(hasReasoning);

    if (!llmJobId || schools.length === 0 || alreadyHasReasoning) {
      setLlmPollingStatus(null);
      return;
    }

    let cancelled = false;
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
    let attempts = 0;
    const maxAttempts = 14;

    const pollReasoning = async () => {
      attempts += 1;
      try {
        setLlmPollingStatus("queued");
        const response = await fetch(`${API_BASE_URL}/preferences/reasoning/${encodeURIComponent(llmJobId)}`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (!response.ok) {
          throw new Error("LLM reasoning lookup failed");
        }

        const payload = (await response.json()) as ReasoningApiResponse;
        const status = (payload.status || "queued").toLowerCase();

        if (status === "completed") {
          const reasoningMap = payload.reasoning || {};
          const hasReasoningPayload =
            Object.keys(reasoningMap).length > 0 ||
            payload.player_summary !== undefined ||
            Boolean(payload.relax_suggestions && payload.relax_suggestions.length > 0);

          if (hasReasoningPayload) {
            setEvaluation((current) => {
              if (!current) return current;
              const currentPrefs = current.preferences_response || {};
              const currentSchools = currentPrefs.schools || [];
              const mergedSchools = currentSchools.map((school) => {
                const reasoning = findReasoningByName(reasoningMap, school.school_name);
                if (!reasoning) return school;
                return {
                  ...school,
                  llm_reasoning: {
                    summary: reasoning.summary,
                    fit_qualities: reasoning.fit_qualities || [],
                    cautions: reasoning.cautions || [],
                  },
                };
              });

              return {
                ...current,
                preferences_response: {
                  ...currentPrefs,
                  recommendation_summary: {
                    ...(currentPrefs.recommendation_summary || {}),
                    llm_status: "completed",
                    player_summary:
                      payload.player_summary !== undefined
                        ? payload.player_summary
                        : currentPrefs.recommendation_summary?.player_summary,
                    relax_suggestions:
                      payload.relax_suggestions || currentPrefs.recommendation_summary?.relax_suggestions || [],
                  },
                  schools: mergedSchools,
                },
              };
            });
          }
          if (!cancelled) {
            setLlmPollingStatus("completed");
          }
          return;
        }

        if (status === "failed") {
          if (!cancelled) {
            setLlmPollingStatus("failed");
          }
          return;
        }

        if (!cancelled) {
          setLlmPollingStatus(status);
        }

        if (attempts >= maxAttempts) {
          if (!cancelled) {
            setLlmPollingStatus("timed_out");
          }
          return;
        }

        timeoutHandle = setTimeout(() => {
          void pollReasoning();
        }, 2500);
      } catch {
        if (!cancelled) {
          setLlmPollingStatus("failed");
        }
      }
    };

    void pollReasoning();

    return () => {
      cancelled = true;
      if (timeoutHandle) {
        clearTimeout(timeoutHandle);
      }
    };
  }, [accessToken, evaluation]);

  const schools = useMemo(() => evaluation?.preferences_response?.schools || [], [evaluation?.preferences_response?.schools]);
  const sortedSchools = useMemo(() => {
    const next = [...schools];
    if (sortMode === "playing_time") {
      next.sort((a, b) => {
        const scoreA = a.scores?.playing_time_score ?? a.playing_time?.percentile ?? -1;
        const scoreB = b.scores?.playing_time_score ?? b.playing_time?.percentile ?? -1;
        return scoreB - scoreA;
      });
    } else if (sortMode === "preferences") {
      next.sort((a, b) => {
        const hitsA = a.match_analysis?.total_nice_to_have_matches ?? a.scores?.nice_to_have_count ?? 0;
        const hitsB = b.match_analysis?.total_nice_to_have_matches ?? b.scores?.nice_to_have_count ?? 0;
        return hitsB - hitsA;
      });
    }
    return next;
  }, [schools, sortMode]);

  useEffect(() => {
    if (sortedSchools.length === 0) {
      setSelectedSchoolId(null);
      return;
    }

    const selectedStillExists = selectedSchoolId
      ? sortedSchools.some((school) => schoolIdentity(school) === selectedSchoolId)
      : false;

    if (!selectedStillExists) {
      setSelectedSchoolId(schoolIdentity(sortedSchools[0]));
    }
  }, [selectedSchoolId, sortedSchools]);

  const selectedSchool = useMemo(() => {
    if (sortedSchools.length === 0) return null;
    if (!selectedSchoolId) return sortedSchools[0];
    return sortedSchools.find((school) => schoolIdentity(school) === selectedSchoolId) || sortedSchools[0];
  }, [selectedSchoolId, sortedSchools]);

  const preferenceEntries = useMemo(() => getPreferenceEntries(evaluation?.preferences_input), [evaluation?.preferences_input]);
  const playerName = useMemo(() => getPlayerName(evaluation?.identity_input), [evaluation?.identity_input]);
  const positionLabel = useMemo(
    () => getPositionLabel(evaluation?.identity_input, evaluation?.stats_input),
    [evaluation?.identity_input, evaluation?.stats_input],
  );
  const preferenceSummary = useMemo(() => getPreferenceSummary(preferenceEntries), [preferenceEntries]);
  const recommendationSummary = evaluation?.preferences_response?.recommendation_summary;
  const activeLlmStatus = (llmPollingStatus || recommendationSummary?.llm_status || "").toLowerCase();

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading evaluation report...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Evaluation Report</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl">{playerName}</h1>
              <p className="mt-3 text-[var(--muted)]">
                Classification:{" "}
                <span className="font-semibold text-[var(--navy)]">
                  {evaluation?.prediction_response?.final_prediction || "Unavailable"}
                </span>
                {" · "}
                Position: <span className="font-semibold text-[var(--navy)]">{positionLabel}</span>
              </p>
              <p className="mt-1 text-sm text-[var(--muted)]">Preferences: {preferenceSummary}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {evaluation?.created_at ? new Date(evaluation.created_at).toLocaleString() : "Timestamp unavailable"}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/evaluations"
                className="rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2.5 text-sm font-semibold text-[var(--navy)]"
              >
                All evaluations
              </Link>
              <Link
                href="/predict"
                className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-strong"
              >
                Run new evaluation
              </Link>
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          )}

          <section className="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Selected preferences</p>
              {preferenceEntries.length === 0 ? (
                <p className="mt-3 text-sm text-[var(--muted)]">
                  No explicit preferences were selected for this run. Schools were ranked from baseline fit and playing-time logic.
                </p>
              ) : (
                <div className="mt-4 space-y-2">
                  {preferenceEntries.map((entry) => (
                    <div key={entry.label} className="rounded-xl border border-[var(--stroke)] bg-white/80 p-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{entry.label}</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--navy)]">{entry.value}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Report summary</p>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <div className="rounded-xl border border-[var(--stroke)] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Classification</p>
                  <p className="mt-1 text-lg font-semibold">{evaluation?.prediction_response?.final_prediction || "-"}</p>
                </div>
                <div className="rounded-xl border border-[var(--stroke)] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Schools returned</p>
                  <p className="mt-1 text-lg font-semibold">{evaluation?.preferences_response?.summary?.total_matches ?? schools.length}</p>
                </div>
                <div className="rounded-xl border border-[var(--stroke)] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Player / Position</p>
                  <p className="mt-1 text-sm font-semibold">{playerName}</p>
                  <p className="text-sm text-[var(--muted)]">{positionLabel}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="mt-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">School matches</p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Click a school to open the detailed fit panel with full breakdown and LLM reasoning.
                </p>
              </div>
              <label className="text-sm font-semibold text-[var(--navy)]">
                Sort
                <select
                  value={sortMode}
                  onChange={(event) => setSortMode(event.target.value as SortMode)}
                  className="form-control mt-2 min-w-[250px]"
                >
                  <option value="default">Default ranking</option>
                  <option value="playing_time">Playing time (high to low)</option>
                  <option value="preferences">Preferences hit (high to low)</option>
                </select>
              </label>
            </div>

            {sortedSchools.length === 0 ? (
              <div className="mt-4 rounded-2xl border border-[var(--stroke)] bg-white/75 p-6">
                <p className="text-sm font-semibold">No schools were returned for this run.</p>
              </div>
            ) : (
              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="space-y-3">
                  {sortedSchools.map((school, index) => {
                    const id = schoolIdentity(school);
                    const isActive = selectedSchoolId === id;
                    return (
                      <button
                        key={`${id}-${index}`}
                        type="button"
                        onClick={() => setSelectedSchoolId(id)}
                        className={`w-full rounded-2xl border bg-white/80 p-4 text-left shadow-soft transition duration-200 ${
                          isActive
                            ? "border-[var(--primary)] ring-1 ring-[var(--primary)]"
                            : "border-[var(--stroke)] hover:-translate-y-0.5 hover:border-[var(--primary)]/40"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-base font-semibold text-[var(--foreground)]">{school.school_name}</p>
                          <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                            {school.division_group || "Division unavailable"}
                          </span>
                        </div>
                        <div className="mt-3 grid gap-2 text-sm text-[var(--muted)]">
                          <p>
                            Nice-to-have hits: <span className="font-semibold text-[var(--navy)]">{school.match_analysis?.total_nice_to_have_matches ?? 0}</span>
                          </p>
                          <p>
                            Playing-time calc: <span className="font-semibold text-[var(--navy)]">{getPlayingTimePreview(school)}</span>
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>

                <aside className="glass rounded-2xl p-5 shadow-soft lg:sticky lg:top-24 lg:max-h-[76vh] lg:overflow-hidden">
                  {selectedSchool ? (
                    <div key={schoolIdentity(selectedSchool)} className="school-detail-panel flex h-full flex-col">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-lg font-semibold">{selectedSchool.school_name}</p>
                        <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                          {selectedSchool.division_group || "Division unavailable"}
                        </span>
                      </div>

                      <p className="mt-2 text-sm text-[var(--muted)]">
                        {selectedSchool.location?.state ? `State: ${selectedSchool.location.state} · ` : ""}
                        {selectedSchool.academics?.grade ? `Academics: ${selectedSchool.academics.grade} · ` : ""}
                        {selectedSchool.athletics?.grade
                          ? `Athletics: ${selectedSchool.athletics.grade}`
                          : "Athletics grade unavailable"}
                      </p>

                      <div className="mt-4 space-y-3 overflow-y-auto pr-1 lg:max-h-[62vh]">
                        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Playing time calc</p>
                          {selectedSchool.playing_time?.available ? (
                            <>
                              <p className="mt-1 text-sm font-semibold text-[var(--navy)]">
                                {selectedSchool.playing_time.bucket || "Estimate available"}
                                {typeof selectedSchool.playing_time.percentile === "number"
                                  ? ` · ${selectedSchool.playing_time.percentile.toFixed(1)} percentile`
                                  : ""}
                              </p>
                              <p className="mt-1 text-sm text-[var(--muted)]">
                                {selectedSchool.playing_time.interpretation || "No interpretation available"}
                              </p>
                              {selectedSchool.playing_time.breakdown && Object.keys(selectedSchool.playing_time.breakdown).length > 0 && (
                                <div className="mt-2 space-y-1 text-xs text-[var(--muted)]">
                                  {Object.entries(selectedSchool.playing_time.breakdown)
                                    .slice(0, 4)
                                    .map(([metric, value]) => (
                                      <p key={metric}>
                                        {metric.replace(/_/g, " ")}: {typeof value === "number" ? value.toFixed(2) : String(value)}
                                      </p>
                                    ))}
                                </div>
                              )}
                            </>
                          ) : (
                            <p className="mt-1 text-sm text-[var(--muted)]">
                              {selectedSchool.playing_time?.message || "Playing-time analysis unavailable for this school"}
                            </p>
                          )}
                        </div>

                        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Preference hits</p>
                          <p className="mt-1 text-sm font-semibold text-[var(--navy)]">
                            {selectedSchool.match_analysis?.total_nice_to_have_matches ?? 0} matched preferences
                          </p>
                          <p className="mt-1 text-sm text-[var(--muted)]">
                            Score:{" "}
                            {typeof selectedSchool.scores?.playing_time_score === "number"
                              ? selectedSchool.scores.playing_time_score.toFixed(1)
                              : "N/A"}{" "}
                            playing-time
                          </p>
                        </div>

                        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Why this matches</p>
                          {selectedSchool.match_analysis?.pros?.length ? (
                            <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                              {selectedSchool.match_analysis.pros.map((pro, index) => (
                                <li key={`${pro.preference}-${index}`}>- {pro.description || pro.preference}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-sm text-[var(--muted)]">No preference matches recorded.</p>
                          )}
                        </div>

                        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Tradeoffs</p>
                          {selectedSchool.match_analysis?.cons?.length ? (
                            <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                              {selectedSchool.match_analysis.cons.map((con, index) => (
                                <li key={`${con.preference}-${index}`}>- {con.reason || con.preference}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-sm text-[var(--muted)]">No major preference tradeoffs detected.</p>
                          )}
                        </div>

                        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">School reasoning</p>
                            {(activeLlmStatus === "queued" || activeLlmStatus === "pending" || activeLlmStatus === "started") && (
                              <span className="text-xs text-[var(--muted)]">Generating...</span>
                            )}
                          </div>

                          {hasReasoning(selectedSchool) ? (
                            <>
                              {selectedSchool.llm_reasoning?.summary && (
                                <p className="mt-2 text-sm text-[var(--foreground)]">{selectedSchool.llm_reasoning.summary}</p>
                              )}
                            </>
                          ) : (
                            <p className="mt-2 text-sm text-[var(--muted)]">
                              {activeLlmStatus === "failed" || activeLlmStatus === "unavailable" || activeLlmStatus === "timed_out"
                                ? "Reasoning is currently unavailable for this run."
                                : "Reasoning will appear here when generation finishes."}
                            </p>
                          )}
                        </div>

                        {recommendationSummary?.player_summary && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Player summary</p>
                            <p className="mt-2 text-sm text-[var(--foreground)]">{recommendationSummary.player_summary}</p>
                          </div>
                        )}

                        {recommendationSummary?.relax_suggestions && recommendationSummary.relax_suggestions.length > 0 && (
                          <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                            <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Relax suggestions</p>
                            <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                              {recommendationSummary.relax_suggestions.map((suggestion, index) => (
                                <li key={`${suggestion.preference || "suggestion"}-${index}`}>
                                  - {suggestion.preference}: {suggestion.suggestion}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                      <p className="text-sm text-[var(--muted)]">Select a school to view the full fit report.</p>
                    </div>
                  )}
                </aside>
              </div>
            )}
          </section>
        </div>
      </main>

      <style jsx>{`
        .school-detail-panel {
          animation: fadeSlideIn 220ms ease;
        }

        @keyframes fadeSlideIn {
          from {
            opacity: 0;
            transform: translateX(14px);
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
