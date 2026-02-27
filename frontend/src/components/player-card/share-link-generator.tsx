"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ShareLink = {
  id: string;
  slug: string;
  platform?: string | null;
  label?: string | null;
  created_at?: string;
  share_url?: string;
  clicks_total?: number;
  clicks_unique?: number;
};

type AnalyticsResponse = {
  share_links?: ShareLink[];
};

type ShareLinkGeneratorProps = {
  accessToken: string;
};

const platformOptions = ["instagram", "twitter", "general"] as const;

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function ShareLinkGenerator({ accessToken }: ShareLinkGeneratorProps) {
  const [platform, setPlatform] = useState<(typeof platformOptions)[number]>("general");
  const [label, setLabel] = useState("");
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    }),
    [accessToken],
  );

  const loadLinks = useCallback(async () => {
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/cards/me/analytics`, { headers });
      const data = (await response.json()) as AnalyticsResponse | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in data ? data.detail || "Failed to load links." : "Failed to load links.");
      }
      setLinks((data as AnalyticsResponse).share_links || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load links.");
    }
  }, [headers]);

  useEffect(() => {
    void loadLinks();
  }, [loadLinks]);

  async function handleGenerate() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/cards/me/share`, {
        method: "POST",
        headers,
        body: JSON.stringify({ platform, label: label.trim() || null }),
      });
      const data = (await response.json()) as ShareLink | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in data ? data.detail || "Failed to create link." : "Failed to create link.");
      }
      setLabel("");
      await loadLinks();
      const created = data as ShareLink;
      if (created.share_url) {
        const copied = await copyToClipboard(created.share_url);
        if (copied) {
          setCopiedId(created.id);
          setTimeout(() => setCopiedId(null), 1500);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create link.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy(link: ShareLink) {
    if (!link.share_url) return;
    const copied = await copyToClipboard(link.share_url);
    if (copied) {
      setCopiedId(link.id);
      setTimeout(() => setCopiedId(null), 1500);
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value as (typeof platformOptions)[number])}
          className="form-control"
        >
          {platformOptions.map((option) => (
            <option key={option} value={option}>
              {option[0].toUpperCase() + option.slice(1)}
            </option>
          ))}
        </select>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (optional)"
          className="form-control"
        />
        <button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={loading}
          className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-70"
        >
          {loading ? "Generating..." : "Generate Link"}
        </button>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="space-y-2">
        {links.length === 0 ? <p className="text-sm text-[var(--muted)]">No share links yet.</p> : null}
        {links.map((link) => (
          <div key={link.id} className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-[var(--navy)]">{link.label || link.platform || "Share link"}</p>
                <p className="text-xs text-[var(--muted)]">{link.created_at ? new Date(link.created_at).toLocaleString() : ""}</p>
              </div>
              <div className="text-right text-xs text-[var(--muted)]">
                <p>Total: {link.clicks_total ?? 0}</p>
                <p>Unique: {link.clicks_unique ?? 0}</p>
              </div>
            </div>
            {link.share_url ? (
              <div className="mt-2 flex items-center gap-2">
                <p className="truncate text-xs text-[var(--navy)]">{link.share_url}</p>
                <button
                  type="button"
                  onClick={() => void handleCopy(link)}
                  className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold text-[var(--navy)]"
                >
                  {copiedId === link.id ? "Copied" : "Copy"}
                </button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
