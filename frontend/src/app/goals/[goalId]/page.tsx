"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { DisclaimerBanner } from "@/components/goals/disclaimer-banner";
import { SensitivitySummary } from "@/components/goals/sensitivity-summary";
import { LeverageRankCard } from "@/components/goals/leverage-rank-card";
import { GapToRangeChart } from "@/components/goals/gap-to-range-chart";
import { ProgressTimeline } from "@/components/goals/progress-timeline";
import { StatUpdateForm } from "@/components/goals/stat-update-form";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type GoalDetail = {
  id: string;
  position_track: string;
  target_level: string;
  current_stats: Record<string, number>;
  progress_entries?: Array<{
    id: string;
    stat_name: string;
    stat_value: number;
    recorded_at?: string;
  }>;
};

type SensitivityResults = {
  base_probability: number;
  rankings: Array<{
    stat_name: string;
    display: string;
    unit: string;
    current_value: number;
    max_impact: number;
    steps: Array<{
      delta: number;
      new_value: number;
      new_probability: number;
      probability_change: number;
    }>;
  }>;
};

type GapResponse = {
  stats: Array<{
    stat_name: string;
    display_name: string;
    unit: string;
    current_value: number;
    p10: number;
    p25: number;
    median: number;
    p75: number;
    p90: number;
  }>;
};

type ViewTab = "leverage" | "gap" | "progress";

export default function GoalDetailPage() {
  const { goalId } = useParams<{ goalId: string }>();
  const { loading: authLoading, accessToken, user } = useRequireAuth(`/goals/${goalId}`);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [goal, setGoal] = useState<GoalDetail | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityResults | null>(null);
  const [gap, setGap] = useState<GapResponse | null>(null);
  const [tab, setTab] = useState<ViewTab>("leverage");

  const loadAll = useCallback(async () => {
    if (!accessToken || !goalId) return;

    setLoading(true);
    setError("");
    try {
      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      };

      const [goalResp, sensitivityResp, gapResp] = await Promise.all([
        fetch(`${API_BASE_URL}/goals/${goalId}`, { headers }),
        fetch(`${API_BASE_URL}/goals/${goalId}/sensitivity`, { headers }),
        fetch(`${API_BASE_URL}/goals/${goalId}/gap-to-range`, { headers }),
      ]);

      const goalData = (await goalResp.json()) as GoalDetail | { detail?: string };
      const sensitivityData = (await sensitivityResp.json()) as { results?: SensitivityResults; detail?: string };
      const gapData = (await gapResp.json()) as GapResponse | { detail?: string };

      if (!goalResp.ok) throw new Error("detail" in goalData ? goalData.detail || "Failed to load goal." : "Failed to load goal.");
      if (!sensitivityResp.ok) {
        throw new Error("detail" in sensitivityData ? sensitivityData.detail || "Failed to load sensitivity." : "Failed to load sensitivity.");
      }
      if (!gapResp.ok) throw new Error("detail" in gapData ? gapData.detail || "Failed to load gap analysis." : "Failed to load gap analysis.");

      setGoal(goalData as GoalDetail);
      setSensitivity((sensitivityData.results || null) as SensitivityResults | null);
      setGap(gapData as GapResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load goal detail.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, goalId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const timelinePoints = useMemo(() => {
    const entries = [...(goal?.progress_entries || [])].sort((a, b) => {
      const left = a.recorded_at ? new Date(a.recorded_at).getTime() : 0;
      const right = b.recorded_at ? new Date(b.recorded_at).getTime() : 0;
      return left - right;
    });

    return entries.map((entry) => ({
      label: entry.recorded_at ? new Date(entry.recorded_at).toLocaleDateString() : entry.stat_name,
      value: Number(entry.stat_value),
    }));
  }, [goal?.progress_entries]);

  const updateFormStats = useMemo(
    () =>
      (sensitivity?.rankings || []).map((ranking) => ({
        statName: ranking.stat_name,
        displayName: ranking.display,
        currentValue: ranking.current_value,
        unit: ranking.unit,
      })),
    [sensitivity?.rankings],
  );

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading goal detail...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Goal Detail</p>
              <h1 className="display-font mt-2 text-4xl md:text-5xl">{goal?.position_track} · {goal?.target_level}</h1>
            </div>

            <div className="flex flex-wrap gap-2">
              {(["leverage", "gap", "progress"] as ViewTab[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTab(value)}
                  className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] ${tab === value ? "bg-[var(--primary)] text-white" : "border border-[var(--stroke)] bg-white/80 text-[var(--navy)]"}`}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>

          {error ? <div className="mt-5 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}

          {tab === "leverage" ? (
            <section className="mt-8 space-y-4">
              <DisclaimerBanner />
              <SensitivitySummary baseProbability={sensitivity?.base_probability || 0} rankings={sensitivity?.rankings || []} />
              <div className="space-y-3">
                {(sensitivity?.rankings || []).map((ranking, index) => (
                  <LeverageRankCard
                    key={ranking.stat_name}
                    rank={index + 1}
                    statName={ranking.stat_name}
                    displayName={ranking.display}
                    unit={ranking.unit}
                    currentValue={ranking.current_value}
                    maxImpact={ranking.max_impact}
                    steps={ranking.steps}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {tab === "gap" ? (
            <section className="mt-8 space-y-4">
              <DisclaimerBanner />
              <GapToRangeChart
                stats={(gap?.stats || []).map((stat) => ({
                  statName: stat.stat_name,
                  displayName: stat.display_name,
                  unit: stat.unit,
                  currentValue: stat.current_value,
                  p10: stat.p10,
                  p25: stat.p25,
                  median: stat.median,
                  p75: stat.p75,
                  p90: stat.p90,
                }))}
              />
            </section>
          ) : null}

          {tab === "progress" ? (
            <section className="mt-8 grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
              <ProgressTimeline points={timelinePoints} title="Logged Progress" />
              {goal && accessToken ? (
                <StatUpdateForm goalId={goal.id} accessToken={accessToken} stats={updateFormStats} onLogged={() => void loadAll()} />
              ) : null}
            </section>
          ) : null}
        </div>
      </main>
    </div>
  );
}
