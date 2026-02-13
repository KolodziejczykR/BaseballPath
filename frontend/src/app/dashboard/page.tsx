"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AccountResponse = {
  profile?: {
    full_name?: string | null;
  };
  plan?: {
    tier?: string;
    remaining_evals?: number | null;
    monthly_eval_limit?: number | null;
  };
  usage?: {
    eval_count?: number;
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
};

export default function DashboardPage() {
  const { loading: authLoading, accessToken } = useRequireAuth("/dashboard");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [account, setAccount] = useState<AccountResponse | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationRecord[]>([]);

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

        const [accountResp, evaluationsResp] = await Promise.all([
          fetch(`${API_BASE_URL}/account/me`, { headers }),
          fetch(`${API_BASE_URL}/evaluations?limit=10&offset=0`, { headers }),
        ]);

        const accountData = (await accountResp.json()) as AccountResponse | { detail?: string };
        const evaluationsData = (await evaluationsResp.json()) as EvaluationListResponse | { detail?: string };

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

        if (!mounted) return;
        setAccount(accountData as AccountResponse);
        setEvaluations(((evaluationsData as EvaluationListResponse).items || []) as EvaluationRecord[]);
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

  const lastRun = useMemo(() => (evaluations.length > 0 ? evaluations[0] : null), [evaluations]);
  const savedSchools = useMemo(() => {
    const names = new Set<string>();
    for (const run of evaluations) {
      for (const school of run.top_schools_snapshot || []) {
        if (school.school_name) {
          names.add(school.school_name);
        }
      }
    }
    return names.size;
  }, [evaluations]);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Dashboard</p>
            <h1 className="display-font mt-4 text-4xl md:text-5xl">Your recruiting command center.</h1>
            <p className="mt-3 text-[var(--muted)]">
              Launch new evaluations, track results, and manage your plan entitlements.
            </p>
          </div>
          <Link
            href="/predict"
            className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong"
          >
            Start New Evaluation
          </Link>
        </div>

        {error && (
          <div className="mt-6 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        )}

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <div className="glass rounded-2xl p-6 shadow-soft">
            <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Last run</p>
            <p className="mt-3 text-xl font-semibold">
              {lastRun?.prediction_response?.final_prediction || "No evaluations yet"}
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {lastRun?.created_at
                ? `Ran on ${new Date(lastRun.created_at).toLocaleString()}`
                : "Start your first evaluation to see school matches here."}
            </p>
          </div>
          <div className="glass rounded-2xl p-6 shadow-soft">
            <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Plan status</p>
            <p className="mt-3 text-xl font-semibold">
              {(account?.plan?.tier || "starter").toUpperCase()}
              {typeof account?.plan?.remaining_evals === "number" && typeof account?.plan?.monthly_eval_limit === "number"
                ? ` · ${account.plan.remaining_evals}/${account.plan.monthly_eval_limit} left`
                : ""}
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">Upgrade for higher monthly limits and premium features.</p>
            <Link
              href="/plans"
              className="mt-4 inline-flex rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold text-[var(--navy)]"
            >
              Manage Plan
            </Link>
          </div>
          <div className="glass rounded-2xl p-6 shadow-soft">
            <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Saved schools</p>
            <p className="mt-3 text-xl font-semibold">{savedSchools}</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Distinct top-school snapshots across your recent evaluations.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
