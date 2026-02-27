"use client";

import { useMemo, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type StatUpdateFormProps = {
  goalId: string;
  accessToken: string;
  stats: Array<{
    statName: string;
    displayName: string;
    currentValue: number;
    unit?: string;
  }>;
  onLogged?: () => void;
};

export function StatUpdateForm({ goalId, accessToken, stats, onLogged }: StatUpdateFormProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const baseline = useMemo(
    () =>
      stats.reduce<Record<string, number>>((acc, stat) => {
        acc[stat.statName] = stat.currentValue;
        return acc;
      }, {}),
    [stats],
  );

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const changed = Object.entries(values)
      .map(([statName, raw]) => ({ statName, value: Number(raw) }))
      .filter(({ statName, value }) => Number.isFinite(value) && value !== baseline[statName]);

    if (changed.length === 0) {
      setError("No changed values to submit.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");
    try {
      await Promise.all(
        changed.map(async (item) => {
          const response = await fetch(`${API_BASE_URL}/goals/${goalId}/progress`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
            body: JSON.stringify({ stat_name: item.statName, stat_value: item.value, source: "manual" }),
          });
          const data = (await response.json()) as { detail?: string };
          if (!response.ok) {
            throw new Error(data.detail || `Failed to update ${item.statName}.`);
          }
        }),
      );

      setSuccess("Progress saved.");
      setValues({});
      onLogged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to log progress.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3 rounded-2xl border border-[var(--stroke)] bg-white/80 p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Log Stat Updates</p>
      {stats.length === 0 ? <p className="text-sm text-[var(--muted)]">No editable stats found for this goal.</p> : null}
      {stats.map((stat) => (
        <label key={stat.statName} className="grid gap-1">
          <span className="text-sm font-medium text-[var(--navy)]">
            {stat.displayName} ({stat.unit || ""})
          </span>
          <input
            type="number"
            step="any"
            value={values[stat.statName] ?? ""}
            onChange={(e) => setValues((prev) => ({ ...prev, [stat.statName]: e.target.value }))}
            className="form-control"
            placeholder={`Current: ${stat.currentValue}`}
          />
        </label>
      ))}

      <button
        type="submit"
        disabled={loading}
        className="rounded-full bg-[var(--primary)] px-5 py-2 text-sm font-semibold text-white disabled:opacity-70"
      >
        {loading ? "Saving..." : "Save Updates"}
      </button>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? <p className="text-sm text-[var(--primary)]">{success}</p> : null}
    </form>
  );
}
