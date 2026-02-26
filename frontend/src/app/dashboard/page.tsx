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

const gettingStartedSteps = [
  {
    title: "Complete your account profile",
    desc: "Add graduating class and primary position so your recommendations have context.",
    href: "/account",
    cta: "Update account",
  },
  {
    title: "Run your first evaluation",
    desc: "Use the guided 3-step prediction workflow and save a full recommendation snapshot.",
    href: "/predict",
    cta: "Start evaluation",
  },
  {
    title: "Review and compare past runs",
    desc: "Track how school matches change as your inputs and priorities evolve.",
    href: "/evaluations",
    cta: "See history",
  },
];

export default function DashboardPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/dashboard");
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
  const profileName = account?.profile?.full_name || user?.email?.split("@")[0] || "Player";
  const planTier = (account?.plan?.tier || "starter").toUpperCase();
  const usageLabel =
    typeof account?.plan?.remaining_evals === "number" && typeof account?.plan?.monthly_eval_limit === "number"
      ? `${account.plan.remaining_evals}/${account.plan.monthly_eval_limit} left this month`
      : "Unlimited evaluations";

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
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Logged-in Home</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl">Welcome back, {profileName}.</h1>
              <p className="mt-3 max-w-2xl text-[var(--muted)]">
                This is your recruiting workspace for launching evaluations, reviewing past runs, and managing plan
                access.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/predict"
                className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong"
              >
                Start New Evaluation
              </Link>
              <Link
                href="/account"
                className="rounded-full border border-[var(--stroke)] bg-white/80 px-6 py-3 text-sm font-semibold text-[var(--navy)]"
              >
                Account & Plan
              </Link>
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          )}

          <section className="mt-8 grid gap-6 md:grid-cols-3">
            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Plan</p>
              <p className="mt-3 text-2xl font-semibold">{planTier}</p>
              <p className="mt-2 text-sm text-[var(--muted)]">{usageLabel}</p>
              <Link
                href="/account#billing"
                className="mt-4 inline-flex rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold text-[var(--navy)]"
              >
                Manage plan
              </Link>
            </div>
            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Last run</p>
              <p className="mt-3 text-xl font-semibold">
                {lastRun?.prediction_response?.final_prediction || "No evaluations yet"}
              </p>
              <p className="mt-2 text-sm text-[var(--muted)]">
                {lastRun?.created_at
                  ? `Ran on ${new Date(lastRun.created_at).toLocaleString()}`
                  : "Start your first evaluation to save your first recommendation snapshot."}
              </p>
            </div>
            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Saved schools</p>
              <p className="mt-3 text-2xl font-semibold">{savedSchools}</p>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Distinct top-school snapshots across your recent evaluations.
              </p>
            </div>
          </section>

          <section className="mt-8 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">How to get started</p>
              <div className="mt-4 grid gap-4">
                {gettingStartedSteps.map((step, index) => (
                  <div key={step.title} className="rounded-2xl border border-[var(--stroke)] bg-white/70 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Step {index + 1}</p>
                    <p className="mt-1 font-semibold">{step.title}</p>
                    <p className="mt-1 text-sm text-[var(--muted)]">{step.desc}</p>
                    <Link href={step.href} className="mt-3 inline-flex text-sm font-semibold text-[var(--primary)]">
                      {step.cta}
                    </Link>
                  </div>
                ))}
              </div>
            </div>

            <div id="history" className="glass rounded-2xl p-6 shadow-soft">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Past evaluations</p>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                    {account?.usage?.eval_count ?? 0} this month
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
                        <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--muted)]">Open run ID: {run.id}</p>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
