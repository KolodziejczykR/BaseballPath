"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type EvaluationListItem = {
  id: string;
  created_at?: string;
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

export default function EvaluationsPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/evaluations");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [items, setItems] = useState<EvaluationListItem[]>([]);

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

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading evaluations...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Past Evaluations</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl">Your saved evaluation history.</h1>
              <p className="mt-3 max-w-2xl text-[var(--muted)]">
                Open any run ID to view the full report, preference hits, and playing-time breakdown.
              </p>
            </div>
            <Link
              href="/predict"
              className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-strong"
            >
              Run New Evaluation
            </Link>
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
                const topSchool = run.top_schools_snapshot?.[0]?.school_name;
                const totalMatches = run.preferences_response?.summary?.total_matches;
                return (
                  <Link
                    key={run.id}
                    href={`/evaluations/${run.id}`}
                    className="block rounded-2xl border border-[var(--stroke)] bg-white/80 p-4 shadow-soft transition hover:-translate-y-0.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold">{run.prediction_response?.final_prediction || "Evaluation complete"}</p>
                      <span className="text-xs text-[var(--muted)]">
                        {run.created_at ? new Date(run.created_at).toLocaleString() : "Timestamp unavailable"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {topSchool ? `Top match: ${topSchool}` : "No top-school snapshot available"}
                    </p>
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {typeof totalMatches === "number" ? `${totalMatches} matches` : "Matches unavailable"} · Run ID: {run.id}
                    </p>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
