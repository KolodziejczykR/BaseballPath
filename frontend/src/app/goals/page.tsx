"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type GoalSummary = {
  id: string;
  position_track: string;
  target_level: string;
  updated_at?: string;
  summary?: {
    current_probability?: number;
    top_leverage_stat?: string | null;
    top_leverage_display?: string | null;
  };
};

type GoalsResponse = {
  items: GoalSummary[];
};

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export default function GoalsPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/goals");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [goals, setGoals] = useState<GoalSummary[]>([]);

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadGoals() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/goals`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        const data = (await response.json()) as GoalsResponse | { detail?: string };
        if (!response.ok) {
          throw new Error("detail" in data ? data.detail || "Failed to load goals." : "Failed to load goals.");
        }
        if (!mounted) return;
        setGoals((data as GoalsResponse).items || []);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load goals.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void loadGoals();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading goals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 pt-5 pb-10 md:pt-6 md:pb-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="display-font mt-2 text-4xl md:text-5xl">Goals & Improvement</h1>
            </div>
            <Link
              href="/goals/create"
              className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold !text-white shadow-strong"
            >
              Add New Goal Set
            </Link>
          </div>

          {error ? <div className="mt-5 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}

          {goals.length === 0 ? (
            <div className="mt-8 rounded-2xl border border-[var(--stroke)] bg-white/80 p-6">
              <p className="text-sm font-semibold text-[var(--navy)]">No goals yet.</p>
              <p className="mt-1 text-sm text-[var(--muted)]">Set up your first goal set to track leverage stats and progress.</p>
              <Link
                href="/goals/create"
                className="mt-4 inline-flex rounded-full bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white"
              >
                Set Up Goals
              </Link>
            </div>
          ) : (
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {goals.map((goal) => (
                <Link key={goal.id} href={`/goals/${goal.id}`} className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-5 shadow-soft transition hover:-translate-y-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">{titleCase(goal.position_track)}</span>
                    <span className="text-xs text-[var(--muted)]">{goal.target_level}</span>
                  </div>

                  <p className="mt-3 text-sm text-[var(--muted)]">
                    Current probability: {typeof goal.summary?.current_probability === "number" ? `${(goal.summary.current_probability * 100).toFixed(1)}%` : "Not computed"}
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
          )}
        </div>
      </main>
    </div>
  );
}
