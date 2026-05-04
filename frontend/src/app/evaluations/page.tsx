"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type EvaluationListItem = {
  id: string;
  created_at?: string;
  position_track?: string;
  identity_input?: Record<string, unknown>;
  preferences_input?: Record<string, unknown>;
  prediction_response?: {
    final_prediction?: string;
  };
  top_schools_snapshot?: Array<{ school_name?: string }>;
  preferences_response?: {
    summary?: {
      total_matches?: number;
    };
  };
};

type EvaluationListResponse = {
  items: EvaluationListItem[];
  total?: number;
};

// Mirrors BUDGET_OPTIONS in /predict/page.tsx — every value is a max threshold.
// Legacy "$65K+" key kept so old runs render correctly.
const BUDGET_LABELS: Record<string, string> = {
  under_20k: "Up to $20K",
  "20k_35k": "Up to $35K",
  "35k_50k": "Up to $50K",
  "50k_65k": "Up to $65K",
  "65k_plus": "$65K+",
};

const RANKING_LABELS: Record<string, string> = {
  baseball_fit: "Best baseball fit",
  academics: "Best academics",
};

function toDisplayValue(value: unknown): string {
  if (Array.isArray(value)) {
    const items = value.filter(Boolean).map((item) => String(item).trim()).filter(Boolean);
    return items.join(", ");
  }
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : "";
  return String(value).trim();
}

function getPositionLabel(run: EvaluationListItem): string {
  const primaryPosition = toDisplayValue(run.identity_input?.primary_position);
  if (primaryPosition) return primaryPosition;

  const track = toDisplayValue(run.position_track).toLowerCase();
  if (!track) return "Position unavailable";
  return `${track.charAt(0).toUpperCase()}${track.slice(1)}`;
}

// Mirrors tierDisplayLabel in /evaluations/[runId]/page.tsx so the list view
// uses the same friendly division names as the detail view.
function tierDisplayLabel(tier: string | undefined): string {
  if (!tier) return "Classification unavailable";
  if (tier.includes("Power 4")) return "Power 4";
  if (tier.includes("Non-P4")) return "Division 1";
  if (tier.includes("Non-D1")) return "D2 & D3";
  return tier;
}

function getTopMatch(run: EvaluationListItem): string | null {
  const name = run.top_schools_snapshot?.[0]?.school_name;
  return typeof name === "string" && name.trim() ? name.trim() : null;
}

function getRegionsLabel(run: EvaluationListItem): string | null {
  const v = run.preferences_input?.regions;
  if (!Array.isArray(v)) return null;
  const items = v.filter((x): x is string => typeof x === "string" && x.trim().length > 0);
  return items.length > 0 ? items.join(", ") : null;
}

function getStatesLabel(run: EvaluationListItem): string | null {
  const v = run.preferences_input?.states;
  if (!Array.isArray(v)) return null;
  const items = v.filter((x): x is string => typeof x === "string" && x.trim().length > 0);
  return items.length > 0 ? items.join(", ") : null;
}

function getRankingLabel(run: EvaluationListItem): string | null {
  const v = run.preferences_input?.ranking_priority;
  if (typeof v !== "string" || !v.trim()) return null;
  return RANKING_LABELS[v] ?? v.replace(/_/g, " ");
}

function getBudgetLabel(run: EvaluationListItem): string | null {
  const v = run.preferences_input?.max_budget;
  if (typeof v !== "string" || !v.trim() || v === "no_preference") return null;
  return BUDGET_LABELS[v] ?? v;
}

export default function EvaluationsPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/evaluations");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [items, setItems] = useState<EvaluationListItem[]>([]);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [resettingAll, setResettingAll] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadEvaluations() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/evaluations?limit=50&offset=0`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        const data = (await response.json()) as EvaluationListResponse | { detail?: string };
        if (!response.ok) {
          throw new Error(
            typeof data === "object" && data && "detail" in data ? data.detail || "Failed to load evaluations." : "Failed to load evaluations.",
          );
        }
        if (!mounted) return;
        setItems((data as EvaluationListResponse).items || []);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load evaluations.");
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    }

    loadEvaluations();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  async function deleteRun(runId: string) {
    if (!accessToken || deletingRunId || resettingAll) return;
    const confirmed = window.confirm("Delete this evaluation run?");
    if (!confirmed) return;

    setDeletingRunId(runId);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/evaluations/${runId}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to delete evaluation run.");
      }
      setItems((current) => current.filter((item) => item.id !== runId));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete evaluation run.");
    } finally {
      setDeletingRunId(null);
    }
  }

  async function resetEvaluationHistory() {
    if (!accessToken || resettingAll || deletingRunId) return;
    const confirmed = window.confirm(
      "Delete all evaluation runs in this account? This cannot be undone.",
    );
    if (!confirmed) return;

    setResettingAll(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/evaluations?confirm=true`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to reset evaluation history.");
      }
      setItems([]);
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : "Failed to reset evaluation history.");
    } finally {
      setResettingAll(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-2xl border border-[var(--cool-stroke)] bg-white p-10 text-center shadow-cool">
          <p className="text-sm text-[var(--cool-ink-muted)]">Loading evaluations...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 pt-10 pb-10 md:pt-14 md:pb-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">Past Evaluations</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight">
                Your evaluation history.
              </h1>
              <p className="mt-4 text-base text-[var(--cool-ink-muted)] leading-relaxed">
                Open any past evaluation to review your top matches.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={resetEvaluationHistory}
                disabled={resettingAll || Boolean(deletingRunId) || items.length === 0}
                className="rounded-full border border-red-300 bg-white px-5 py-2.5 text-sm font-semibold text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {resettingAll ? "Resetting..." : "Reset History"}
              </button>
              <Link
                href="/predict"
                className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold !text-white shadow-strong"
              >
                Run New Evaluation
              </Link>
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          )}

          {items.length === 0 ? (
            <div className="mt-8 rounded-2xl border border-[var(--stroke)] bg-white/75 p-6">
              <p className="text-sm font-semibold">No saved evaluations yet.</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Start your first run from the prediction pipeline and it will appear here.
              </p>
            </div>
          ) : (
            <div className="mt-8 space-y-3">
              {items.map((run) => {
                const topSchool = getTopMatch(run);
                const positionLabel = getPositionLabel(run);
                const divisionLabel = tierDisplayLabel(run.prediction_response?.final_prediction);
                const regionsLabel = getRegionsLabel(run);
                const statesLabel = getStatesLabel(run);
                const rankingLabel = getRankingLabel(run);
                const budgetLabel = getBudgetLabel(run);
                const hasPreferences = Boolean(regionsLabel || statesLabel || rankingLabel || budgetLabel);
                return (
                  <div
                    key={run.id}
                    className="rounded-2xl border border-[var(--cool-stroke)] bg-white px-5 pt-5 pb-3 shadow-cool"
                  >
                    <Link
                      href={`/evaluations/${run.id}`}
                      className="block transition hover:-translate-y-0.5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <p className="text-base font-semibold text-[var(--cool-ink)]">
                          {topSchool ? `Top match: ${topSchool}` : "Top match unavailable"}
                        </p>
                        <span className="text-xs text-[var(--cool-ink-muted)]">
                          {run.created_at ? new Date(run.created_at).toLocaleString() : "Timestamp unavailable"}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm text-[var(--cool-ink-muted)]">
                        {positionLabel} · {divisionLabel}
                      </p>
                      {hasPreferences && (
                        <div className="mt-3">
                          <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--cool-ink-muted)] font-semibold mb-1.5">
                            Preferences
                          </p>
                          <div className="space-y-1 text-xs text-[var(--cool-ink-muted)]">
                            {regionsLabel && (
                              <p>
                                <span className="font-semibold text-[var(--cool-ink)]">Regions:</span> {regionsLabel}
                              </p>
                            )}
                            {statesLabel && (
                              <p>
                                <span className="font-semibold text-[var(--cool-ink)]">States:</span> {statesLabel}
                              </p>
                            )}
                            {rankingLabel && (
                              <p>
                                <span className="font-semibold text-[var(--cool-ink)]">Ranking:</span> {rankingLabel}
                              </p>
                            )}
                            {budgetLabel && (
                              <p>
                                <span className="font-semibold text-[var(--cool-ink)]">Budget:</span> {budgetLabel}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </Link>
                    <div className="mt-2 flex justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          void deleteRun(run.id);
                        }}
                        disabled={deletingRunId === run.id || resettingAll}
                        className="rounded-full border border-red-200 bg-white px-3 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {deletingRunId === run.id ? "Removing..." : "Remove Run"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
