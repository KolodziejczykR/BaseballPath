"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type PositionTrack = "pitcher" | "infielder" | "outfielder" | "catcher";

type EvaluationRecord = {
  id: string;
  position_track?: string;
  identity_input?: Record<string, unknown>;
  stats_input?: Record<string, unknown>;
  created_at?: string;
};

type EvaluationListResponse = {
  items: EvaluationRecord[];
};

const statsConfig: Record<PositionTrack, Array<{ key: string; label: string; unit: string; step: string }>> = {
  infielder: [
    { key: "exit_velo_max", label: "Exit Velocity", unit: "mph", step: "0.1" },
    { key: "inf_velo", label: "Infield Velocity", unit: "mph", step: "0.1" },
    { key: "sixty_time", label: "60-Yard Dash", unit: "sec", step: "0.01" },
  ],
  outfielder: [
    { key: "exit_velo_max", label: "Exit Velocity", unit: "mph", step: "0.1" },
    { key: "of_velo", label: "Outfield Velocity", unit: "mph", step: "0.1" },
    { key: "sixty_time", label: "60-Yard Dash", unit: "sec", step: "0.01" },
  ],
  catcher: [
    { key: "exit_velo_max", label: "Exit Velocity", unit: "mph", step: "0.1" },
    { key: "c_velo", label: "Catcher Velocity", unit: "mph", step: "0.1" },
    { key: "pop_time", label: "Pop Time", unit: "sec", step: "0.01" },
    { key: "sixty_time", label: "60-Yard Dash", unit: "sec", step: "0.01" },
  ],
  pitcher: [
    { key: "fastball_velo_max", label: "Fastball Max", unit: "mph", step: "0.1" },
    { key: "fastball_velo_range", label: "Fastball Avg", unit: "mph", step: "0.1" },
    { key: "fastball_spin", label: "Fastball Spin", unit: "rpm", step: "1" },
    { key: "changeup_velo", label: "Changeup Velo", unit: "mph", step: "0.1" },
    { key: "curveball_velo", label: "Curveball Velo", unit: "mph", step: "0.1" },
    { key: "slider_velo", label: "Slider Velo", unit: "mph", step: "0.1" },
  ],
};

function normalizePosition(track: string | undefined): PositionTrack {
  const lower = (track || "").toLowerCase();
  if (lower === "pitcher" || lower === "infielder" || lower === "outfielder" || lower === "catcher") {
    return lower;
  }
  return "infielder";
}

function toFloatMap(raw: Record<string, string>): Record<string, number> {
  const next: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw)) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      next[key] = numeric;
    }
  }
  return next;
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

export default function GoalsCreatePage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/goals/create");
  const router = useRouter();
  const [fromEval, setFromEval] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [step, setStep] = useState(1);
  const [positionTrack, setPositionTrack] = useState<PositionTrack>("infielder");
  const [targetLevel, setTargetLevel] = useState<"D1" | "Power 4 D1">("D1");
  const [stats, setStats] = useState<Record<string, string>>({});
  const [identityFields, setIdentityFields] = useState<Record<string, string>>({
    height: "",
    weight: "",
    primary_position: "",
    region: "West",
    throwing_hand: "R",
    hitting_handedness: "R",
  });
  const [evaluation, setEvaluation] = useState<EvaluationRecord | null>(null);

  const statFields = useMemo(() => statsConfig[positionTrack], [positionTrack]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const next = new URLSearchParams(window.location.search).get("from_eval") || "";
    setFromEval(next);
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadEvaluationPrefill() {
      setLoading(true);
      setError("");
      try {
        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        };

        const limit = fromEval ? 20 : 1;
        const response = await fetch(`${API_BASE_URL}/evaluations?limit=${limit}&offset=0`, { headers });
        const data = (await response.json()) as EvaluationListResponse | { detail?: string };
        if (!response.ok) {
          throw new Error("detail" in data ? data.detail || "Failed to load evaluations." : "Failed to load evaluations.");
        }

        const evaluations = (data as EvaluationListResponse).items || [];
        const selected = fromEval ? evaluations.find((item) => item.id === fromEval) || null : evaluations[0] || null;

        if (!mounted) return;
        setEvaluation(selected);

        if (selected) {
          const position = normalizePosition(selected.position_track);
          setPositionTrack(position);

          const nextStats: Record<string, string> = {};
          for (const field of statsConfig[position]) {
            const raw = selected.stats_input?.[field.key];
            if (raw !== null && raw !== undefined) {
              nextStats[field.key] = String(raw);
            }
          }
          setStats(nextStats);

          setIdentityFields((prev) => ({
            ...prev,
            height: stringifyValue(selected.identity_input?.height),
            weight: stringifyValue(selected.identity_input?.weight),
            primary_position: stringifyValue(selected.identity_input?.primary_position),
            region: stringifyValue(selected.identity_input?.player_region || selected.identity_input?.region || "West"),
            throwing_hand: stringifyValue(selected.identity_input?.throwing_hand || "R"),
            hitting_handedness: stringifyValue(selected.identity_input?.hitting_handedness || "R"),
          }));
        }
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load prefill data.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void loadEvaluationPrefill();
    return () => {
      mounted = false;
    };
  }, [accessToken, fromEval]);

  async function handleCreateGoal() {
    if (!accessToken) return;

    setSubmitting(true);
    setError("");
    try {
      const payload = {
        position_track: positionTrack,
        target_level: targetLevel,
        current_stats: toFloatMap(stats),
        identity_fields: {
          ...identityFields,
          height: Number(identityFields.height),
          weight: Number(identityFields.weight),
        },
        evaluation_run_id: evaluation?.id || null,
      };

      const response = await fetch(`${API_BASE_URL}/goals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(payload),
      });
      const data = (await response.json()) as { id?: string; detail?: string };
      if (!response.ok || !data.id) {
        throw new Error(data.detail || "Failed to create goal.");
      }

      router.push(`/goals/${data.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create goal.");
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading goal creator...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-4xl">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Goal Creation</p>
              <h1 className="display-font mt-2 text-4xl md:text-5xl">Create Goal Set</h1>
            </div>
            <Link href="/goals" className="rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-sm font-semibold text-[var(--navy)]">
              Back to Goals
            </Link>
          </div>

          {error ? <div className="mt-5 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}

          <section className="glass mt-8 rounded-2xl p-6 shadow-soft">
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setStep(value)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${step === value ? "bg-[var(--primary)] text-white" : "border border-[var(--stroke)] bg-white/80 text-[var(--navy)]"}`}
                >
                  Step {value}
                </button>
              ))}
            </div>

            {step === 1 ? (
              <div className="mt-5 space-y-3">
                <label className="grid gap-1">
                  <span className="text-sm font-semibold text-[var(--navy)]">Position Track</span>
                  <select
                    value={positionTrack}
                    onChange={(e) => {
                      const next = e.target.value as PositionTrack;
                      setPositionTrack(next);
                      setStats({});
                    }}
                    className="form-control"
                  >
                    <option value="pitcher">Pitcher</option>
                    <option value="infielder">Infielder</option>
                    <option value="outfielder">Outfielder</option>
                    <option value="catcher">Catcher</option>
                  </select>
                </label>

                <button
                  type="button"
                  onClick={() => {
                    if (!evaluation) return;
                    const next = normalizePosition(evaluation.position_track);
                    setPositionTrack(next);
                    const nextStats: Record<string, string> = {};
                    for (const field of statsConfig[next]) {
                      const raw = evaluation.stats_input?.[field.key];
                      if (raw !== null && raw !== undefined) nextStats[field.key] = String(raw);
                    }
                    setStats(nextStats);
                  }}
                  className="rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-sm font-semibold text-[var(--navy)]"
                >
                  Import from Latest Evaluation
                </button>

                <button type="button" onClick={() => setStep(2)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                  Continue
                </button>
              </div>
            ) : null}

            {step === 2 ? (
              <div className="mt-5 space-y-4">
                <p className="text-sm font-semibold text-[var(--navy)]">Identity Fields</p>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="grid gap-1">
                    <span className="text-xs text-[var(--muted)]">Height</span>
                    <input value={identityFields.height || ""} onChange={(e) => setIdentityFields((prev) => ({ ...prev, height: e.target.value }))} className="form-control" type="number" />
                  </label>
                  <label className="grid gap-1">
                    <span className="text-xs text-[var(--muted)]">Weight</span>
                    <input value={identityFields.weight || ""} onChange={(e) => setIdentityFields((prev) => ({ ...prev, weight: e.target.value }))} className="form-control" type="number" />
                  </label>
                  <label className="grid gap-1">
                    <span className="text-xs text-[var(--muted)]">Primary Position</span>
                    <input value={identityFields.primary_position || ""} onChange={(e) => setIdentityFields((prev) => ({ ...prev, primary_position: e.target.value }))} className="form-control" />
                  </label>
                  <label className="grid gap-1">
                    <span className="text-xs text-[var(--muted)]">Region</span>
                    <input value={identityFields.region || ""} onChange={(e) => setIdentityFields((prev) => ({ ...prev, region: e.target.value }))} className="form-control" />
                  </label>
                  <label className="grid gap-1">
                    <span className="text-xs text-[var(--muted)]">Throwing Hand</span>
                    <input value={identityFields.throwing_hand || ""} onChange={(e) => setIdentityFields((prev) => ({ ...prev, throwing_hand: e.target.value }))} className="form-control" />
                  </label>
                  {positionTrack !== "pitcher" ? (
                    <label className="grid gap-1">
                      <span className="text-xs text-[var(--muted)]">Hitting Handedness</span>
                      <input value={identityFields.hitting_handedness || ""} onChange={(e) => setIdentityFields((prev) => ({ ...prev, hitting_handedness: e.target.value }))} className="form-control" />
                    </label>
                  ) : null}
                </div>

                <p className="text-sm font-semibold text-[var(--navy)]">Current Stats</p>
                <div className="grid gap-3 md:grid-cols-2">
                  {statFields.map((field) => (
                    <label key={field.key} className="grid gap-1">
                      <span className="text-xs text-[var(--muted)]">
                        {field.label} ({field.unit})
                      </span>
                      <input
                        value={stats[field.key] || ""}
                        onChange={(e) => setStats((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        className="form-control"
                        type="number"
                        step={field.step}
                      />
                    </label>
                  ))}
                </div>

                <button type="button" onClick={() => setStep(3)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                  Continue
                </button>
              </div>
            ) : null}

            {step === 3 ? (
              <div className="mt-5 space-y-3">
                <p className="text-sm font-semibold text-[var(--navy)]">Target Level</p>
                <label className="flex items-center gap-2 rounded-xl border border-[var(--stroke)] bg-white/75 p-3 text-sm">
                  <input type="radio" checked={targetLevel === "D1"} onChange={() => setTargetLevel("D1")} /> D1
                </label>
                <label className="flex items-center gap-2 rounded-xl border border-[var(--stroke)] bg-white/75 p-3 text-sm">
                  <input type="radio" checked={targetLevel === "Power 4 D1"} onChange={() => setTargetLevel("Power 4 D1")} />
                  Power 4 D1
                </label>
                <button type="button" onClick={() => setStep(4)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                  Continue
                </button>
              </div>
            ) : null}

            {step === 4 ? (
              <div className="mt-5 space-y-3">
                <p className="text-sm font-semibold text-[var(--navy)]">Preview</p>
                <div className="rounded-xl border border-[var(--stroke)] bg-white/75 p-3 text-sm text-[var(--muted)]">
                  <p>Position: {positionTrack}</p>
                  <p>Target: {targetLevel}</p>
                  <p>Stats entered: {Object.keys(toFloatMap(stats)).length}</p>
                  <p>Evaluation import: {evaluation ? "Yes" : "No"}</p>
                </div>
                <p className="text-xs text-[var(--muted)]">Initial sensitivity rankings will be available immediately after creation.</p>
                <button type="button" onClick={() => setStep(5)} className="rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white">
                  Continue
                </button>
              </div>
            ) : null}

            {step === 5 ? (
              <div className="mt-5 space-y-3">
                <p className="text-sm text-[var(--muted)]">Confirm and create your goal set.</p>
                <button
                  type="button"
                  onClick={() => void handleCreateGoal()}
                  disabled={submitting}
                  className="rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-70"
                >
                  {submitting ? "Creating..." : "Create Goals"}
                </button>
              </div>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}
