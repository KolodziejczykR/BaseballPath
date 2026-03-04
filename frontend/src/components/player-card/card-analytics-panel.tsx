"use client";

import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AnalyticsResponse = {
  total_clicks?: number;
  unique_clicks?: number;
  platform_breakdown?: Record<string, number>;
  recent_clicks?: Array<{
    id: string;
    clicked_at?: string;
    platform_detected?: string;
    referrer?: string;
    is_unique?: boolean;
  }>;
};

type CardAnalyticsPanelProps = {
  accessToken: string;
};

export function CardAnalyticsPanel({ accessToken }: CardAnalyticsPanelProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState<AnalyticsResponse | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_BASE_URL}/cards/me/analytics`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        const payload = (await response.json()) as AnalyticsResponse | { detail?: string };
        if (!response.ok) {
          throw new Error("detail" in payload ? payload.detail || "Failed to load analytics." : "Failed to load analytics.");
        }
        if (!mounted) return;
        setData(payload as AnalyticsResponse);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load analytics.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, [accessToken]);

  if (loading) return <p className="text-sm text-[var(--muted)]">Loading analytics...</p>;

  return (
    <div className="space-y-3">
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Total Clicks</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--navy)]">{data?.total_clicks ?? 0}</p>
        </div>
        <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Unique Clicks</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--navy)]">{data?.unique_clicks ?? 0}</p>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Platform Breakdown</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(data?.platform_breakdown || {}).length === 0 ? (
            <p className="text-sm text-[var(--muted)]">No clicks yet.</p>
          ) : (
            Object.entries(data?.platform_breakdown || {}).map(([platform, count]) => (
              <span key={platform} className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                {platform}: {count}
              </span>
            ))
          )}
        </div>
      </div>

      <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
        <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Recent Clicks</p>
        <div className="mt-2 space-y-2">
          {(data?.recent_clicks || []).length === 0 ? <p className="text-sm text-[var(--muted)]">No recent clicks.</p> : null}
          {(data?.recent_clicks || []).map((click) => (
            <div key={click.id} className="rounded-lg border border-[var(--stroke)] bg-white/80 px-3 py-2 text-xs text-[var(--navy)]">
              <p>
                {click.platform_detected || "general"} · {click.clicked_at ? new Date(click.clicked_at).toLocaleString() : ""}
              </p>
              <p className="truncate text-[var(--muted)]">{click.referrer || "Direct"}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
