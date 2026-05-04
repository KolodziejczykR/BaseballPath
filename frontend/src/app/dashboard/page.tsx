"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AccountResponse = {
  profile?: {
    full_name?: string | null;
    grad_year?: number | null;
    primary_position?: string | null;
  };
};

type EvaluationRecord = {
  id: string;
  created_at?: string;
  prediction_response?: {
    final_prediction?: string;
  };
  top_schools_snapshot?: Array<{ school_name?: string }>;
};

type EvaluationListResponse = {
  items: EvaluationRecord[];
  total?: number | null;
};

type GoalSummary = {
  id: string;
  position_track?: string;
  target_level?: string;
  updated_at?: string;
  summary?: {
    current_probability?: number;
    top_leverage_stat?: string | null;
    top_leverage_display?: string | null;
  };
};

type GoalsListResponse = {
  items: GoalSummary[];
};

type SavedSchoolRecord = {
  id: string;
  school_name: string;
  school_logo_image?: string | null;
  created_at?: string;
  school_data?: {
    school_logo_image?: string | null;
    division_group?: string;
    division_label?: string;
    match_analysis?: {
      total_nice_to_have_matches?: number;
    };
  };
};

type SavedSchoolsResponse = {
  items: SavedSchoolRecord[];
  count?: number;
};

function getNcaLogoUrl(school: SavedSchoolRecord): string | null {
  const logoKey = (school.school_logo_image || school.school_data?.school_logo_image || "").trim();
  if (!logoKey) return null;
  return `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(logoKey)}.svg`;
}

function mapLegacyDivisionGroup(group: string | undefined): string | null {
  if (!group) return null;
  const lowered = group.trim().toLowerCase();
  if (!lowered) return null;
  if (lowered.includes("power") && lowered.includes("4")) return "Power 4";
  if (lowered.includes("non-p4") || lowered.includes("non p4")) return "Division 1";
  if (lowered.includes("non-d1") || lowered.includes("non d1")) return null;
  if (lowered.includes("d3") || lowered.includes("division 3") || lowered.includes("division iii")) return "Division 3";
  if (lowered.includes("d2") || lowered.includes("division 2") || lowered.includes("division ii")) return "Division 2";
  if (lowered.includes("d1") || lowered.includes("division 1") || lowered.includes("division i")) return "Division 1";
  return null;
}

function getDivisionBadgeLabel(school: SavedSchoolRecord): string | null {
  return school.school_data?.division_label || mapLegacyDivisionGroup(school.school_data?.division_group);
}

export default function DashboardPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/dashboard");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [account, setAccount] = useState<AccountResponse | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);
  const [totalEvals, setTotalEvals] = useState(0);
  const [goals, setGoals] = useState<GoalSummary[]>([]);
  const [savedSchools, setSavedSchools] = useState<SavedSchoolRecord[]>([]);

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        };

        const [accountResp, evaluationsResp, goalsResp, savedSchoolsResp] = await Promise.all([
          fetch(`${API_BASE_URL}/account/me`, { headers }),
          fetch(`${API_BASE_URL}/evaluations?limit=10&offset=0`, { headers }),
          fetch(`${API_BASE_URL}/goals`, { headers }),
          fetch(`${API_BASE_URL}/saved-schools`, { headers }),
        ]);

        const accountData = (await accountResp.json()) as AccountResponse | { detail?: string };
        const evaluationsData = (await evaluationsResp.json()) as EvaluationListResponse | { detail?: string };
        const goalsData = (await goalsResp.json()) as GoalsListResponse | { detail?: string };
        const savedSchoolsData = (await savedSchoolsResp.json()) as SavedSchoolsResponse | { detail?: string };

        if (!accountResp.ok) {
          throw new Error(
            typeof accountData === "object" && accountData && "detail" in accountData
              ? accountData.detail || "Failed to load account."
              : "Failed to load account.",
          );
        }
        if (!evaluationsResp.ok) {
          throw new Error(
            typeof evaluationsData === "object" && evaluationsData && "detail" in evaluationsData
              ? evaluationsData.detail || "Failed to load evaluations."
              : "Failed to load evaluations.",
          );
        }
        if (!goalsResp.ok) {
          throw new Error(
            typeof goalsData === "object" && goalsData && "detail" in goalsData
              ? goalsData.detail || "Failed to load goals."
              : "Failed to load goals.",
          );
        }
        if (!savedSchoolsResp.ok) {
          throw new Error(
            typeof savedSchoolsData === "object" && savedSchoolsData && "detail" in savedSchoolsData
              ? savedSchoolsData.detail || "Failed to load saved schools."
              : "Failed to load saved schools.",
          );
        }

        if (!mounted) return;
        setAccount(accountData as AccountResponse);
        const evalList = evaluationsData as EvaluationListResponse;
        setEvaluations((evalList.items || []) as EvaluationRecord[]);
        setTotalEvals(
          typeof evalList.total === "number" ? evalList.total : (evalList.items || []).length,
        );
        setGoals((goalsData as GoalsListResponse).items || []);
        setSavedSchools((savedSchoolsData as SavedSchoolsResponse).items || []);
      } catch (loadError) {
        if (!mounted) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard.");
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  const savedSchoolCount = savedSchools.length;
  const topSavedSchools = useMemo(() => savedSchools.slice(0, 3), [savedSchools]);
  const fullName = account?.profile?.full_name || user?.email?.split("@")[0] || "Player";
  const profileName = fullName.split(" ")[0];

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-2xl border border-[var(--cool-stroke)] bg-white p-10 text-center shadow-cool">
          <p className="text-sm text-[var(--cool-ink-muted)]">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 pt-10 pb-10 md:pt-14 md:pb-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">Dashboard</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight">
                Welcome back, {profileName}.
              </h1>
              <p className="mt-4 text-base text-[var(--cool-ink-muted)] leading-relaxed">
                This is your recruiting headquarters for managing past runs and keeping your saved schools organized.
              </p>
            </div>
            <div className="flex w-full justify-end md:w-auto">
              <Link
                href="/predict"
                className="whitespace-nowrap rounded-full bg-[var(--burnt-sienna)] px-6 py-3 text-sm font-semibold !text-white shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-200"
              >
                Start New Evaluation
              </Link>
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          )}

          <section className="mt-8 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
            <div className="glass rounded-2xl p-6 shadow-soft">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Goals tracker</p>
                <Link
                  href={goals.length > 0 ? "/goals" : "/goals/create"}
                  className="rounded-full bg-[var(--primary)] px-3 py-1 text-xs font-semibold !text-white shadow-strong"
                >
                  {goals.length > 0 ? "View goals" : "Set goals"}
                </Link>
              </div>

              {goals.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {goals.slice(0, 3).map((goal) => (
                    <Link
                      key={goal.id}
                      href={`/goals/${goal.id}`}
                      className="block rounded-2xl border border-[var(--stroke)] bg-white/75 p-4 transition hover:-translate-y-0.5"
                    >
                      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Model outcome goal</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--navy)]">{goal.target_level || "D1"}</p>
                      <p className="mt-1 text-sm text-[var(--muted)]">
                        Current probability:{" "}
                        {typeof goal.summary?.current_probability === "number"
                          ? `${(goal.summary.current_probability * 100).toFixed(1)}%`
                          : "Not computed"}
                      </p>
                      <p className="mt-1 text-sm text-[var(--muted)]">
                        Top leverage: {goal.summary?.top_leverage_display || goal.summary?.top_leverage_stat || "Not available"}
                      </p>
                      <p className="mt-1 text-xs text-[var(--muted)]">
                        Updated: {goal.updated_at ? new Date(goal.updated_at).toLocaleString() : "Unknown"}
                      </p>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-[var(--stroke)] bg-white/75 p-4">
                  <p className="text-sm font-semibold text-[var(--navy)]">No goals created yet.</p>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Set improvement goals to track your model outcome and top leverage stats over time.
                  </p>
                </div>
              )}
            </div>

            <div id="history" className="glass rounded-2xl p-6 shadow-soft">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Past evaluations</p>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                    {totalEvals} total
                  </span>
                  <Link
                    href="/evaluations"
                    className="rounded-full border border-[var(--stroke)] bg-white/80 px-3 py-1 text-xs font-semibold text-[var(--navy)]"
                  >
                    View all
                  </Link>
                </div>
              </div>

              {evaluations.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-[var(--stroke)] bg-white/70 p-5">
                  <p className="text-sm font-semibold">No evaluations saved yet.</p>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Run your first evaluation to build history and compare school fit over time.
                  </p>
                  <Link
                    href="/predict"
                    className="mt-4 inline-flex rounded-full bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white"
                  >
                    Run first evaluation
                  </Link>
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {evaluations.map((run) => {
                    const topSchool = run.top_schools_snapshot?.[0]?.school_name;
                    return (
                      <Link
                        key={run.id}
                        href={`/evaluations/${run.id}`}
                        className="block rounded-2xl border border-[var(--stroke)] bg-white/75 p-4 transition hover:-translate-y-0.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold">
                            {run.prediction_response?.final_prediction || "Evaluation complete"}
                          </p>
                          <span className="text-xs text-[var(--muted)]">
                            {run.created_at ? new Date(run.created_at).toLocaleString() : "Timestamp unavailable"}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                          {topSchool ? `Top match: ${topSchool}` : "No school snapshot attached to this run."}
                        </p>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          <section className="mt-8">
            <div className="glass mx-auto w-full max-w-4xl rounded-2xl p-6 shadow-soft">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Saved schools</p>
                <Link
                  href="/saved-schools"
                  className="rounded-full border border-[var(--stroke)] bg-white/80 px-3 py-1 text-xs font-semibold text-[var(--navy)]"
                >
                  Open list
                </Link>
              </div>
              <p className="mt-3 text-2xl font-semibold">{savedSchoolCount}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">Schools you intentionally saved from evaluations.</p>

              {topSavedSchools.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {topSavedSchools.map((school) => {
                    const logoUrl = getNcaLogoUrl(school);
                    const divisionBadge = getDivisionBadgeLabel(school);
                    return (
                      <Link
                        key={school.id}
                        href="/saved-schools"
                        className="block rounded-xl border border-[var(--stroke)] bg-white/75 p-2.5 transition hover:-translate-y-0.5"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold leading-none text-[var(--navy)]">{school.school_name}</p>
                            <p className="mt-0.5 text-xs leading-tight text-[var(--muted)]">
                              {divisionBadge ? `${divisionBadge} · ` : ""}Matching preferences:{" "}
                              {school.school_data?.match_analysis?.total_nice_to_have_matches ?? 0}
                            </p>
                          </div>
                          {logoUrl ? (
                            <>
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={logoUrl}
                                alt={`${school.school_name} logo`}
                                loading="lazy"
                                onError={(event) => {
                                  event.currentTarget.style.display = "none";
                                }}
                                className="h-10 w-10 rounded-md border border-[var(--stroke)] bg-white/90 p-1 object-contain"
                              />
                            </>
                          ) : null}
                        </div>
                      </Link>
                    );
                  })}
                  {savedSchoolCount > 3 ? (
                    <Link
                      href="/saved-schools"
                      className="inline-flex text-xs font-semibold text-[var(--primary)] hover:underline"
                    >
                      And {savedSchoolCount - 3} more saved schools. Open full list.
                    </Link>
                  ) : null}
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
                  <p className="text-sm text-[var(--muted)]">No saved schools yet. Save one from an evaluation report.</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
