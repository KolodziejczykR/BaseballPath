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
    message?: string | null;
  };
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
    schools?: SchoolResult[];
  };
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
  const text = String(value).trim();
  return text;
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

export default function EvaluationDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { loading: authLoading, accessToken, user } = useRequireAuth(`/evaluations/${runId}`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("default");

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

  const preferenceEntries = useMemo(() => getPreferenceEntries(evaluation?.preferences_input), [evaluation?.preferences_input]);

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
              <h1 className="display-font mt-3 text-4xl md:text-5xl">Run {runId}</h1>
              <p className="mt-3 text-[var(--muted)]">
                Predicted tier:{" "}
                <span className="font-semibold text-[var(--navy)]">
                  {evaluation?.prediction_response?.final_prediction || "Unavailable"}
                </span>
              </p>
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
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Predicted tier</p>
                  <p className="mt-1 text-lg font-semibold">{evaluation?.prediction_response?.final_prediction || "-"}</p>
                </div>
                <div className="rounded-xl border border-[var(--stroke)] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Schools returned</p>
                  <p className="mt-1 text-lg font-semibold">{evaluation?.preferences_response?.summary?.total_matches ?? schools.length}</p>
                </div>
                <div className="rounded-xl border border-[var(--stroke)] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Run ID</p>
                  <p className="mt-1 text-sm font-semibold break-all">{runId}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="mt-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">School matches</p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Sort by playing-time score or preference-hit count to compare opportunities.
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
              <div className="mt-4 space-y-4">
                {sortedSchools.map((school, index) => (
                  <article key={`${school.school_name}-${index}`} className="glass rounded-2xl p-5 shadow-soft">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-lg font-semibold">{school.school_name}</p>
                      <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                        {school.division_group || "Division unavailable"}
                      </span>
                    </div>

                    <p className="mt-2 text-sm text-[var(--muted)]">
                      {school.location?.state ? `State: ${school.location.state} · ` : ""}
                      {school.academics?.grade ? `Academics: ${school.academics.grade} · ` : ""}
                      {school.athletics?.grade ? `Athletics: ${school.athletics.grade}` : "Athletics grade unavailable"}
                    </p>

                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Playing time calc</p>
                        {school.playing_time?.available ? (
                          <>
                            <p className="mt-1 text-sm font-semibold text-[var(--navy)]">
                              {school.playing_time.bucket || "Bucket unavailable"}
                              {typeof school.playing_time.percentile === "number"
                                ? ` · ${school.playing_time.percentile.toFixed(1)} percentile`
                                : ""}
                            </p>
                            <p className="mt-1 text-sm text-[var(--muted)]">
                              {school.playing_time.interpretation || "No interpretation available"}
                            </p>
                          </>
                        ) : (
                          <p className="mt-1 text-sm text-[var(--muted)]">{school.playing_time?.message || "Not available"}</p>
                        )}
                      </div>

                      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Preference hits</p>
                        <p className="mt-1 text-sm font-semibold text-[var(--navy)]">
                          {school.match_analysis?.total_nice_to_have_matches ?? 0} matched preferences
                        </p>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                          Score:{" "}
                          {typeof school.scores?.playing_time_score === "number"
                            ? school.scores.playing_time_score.toFixed(1)
                            : "N/A"}{" "}
                          playing-time
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Why this matches</p>
                        {school.match_analysis?.pros?.length ? (
                          <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                            {school.match_analysis.pros.slice(0, 4).map((pro, proIndex) => (
                              <li key={`${pro.preference}-${proIndex}`}>- {pro.description || pro.preference}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-[var(--muted)]">No preference matches recorded.</p>
                        )}
                      </div>
                      <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Tradeoffs</p>
                        {school.match_analysis?.cons?.length ? (
                          <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
                            {school.match_analysis.cons.slice(0, 4).map((con, conIndex) => (
                              <li key={`${con.preference}-${conIndex}`}>- {con.reason || con.preference}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-[var(--muted)]">No major preference tradeoffs detected.</p>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
