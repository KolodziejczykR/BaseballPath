"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AccountResponse = {
  profile?: {
    full_name?: string | null;
    state?: string | null;
    grad_year?: number | null;
    primary_position?: string | null;
  };
};

type EvaluationsListResponse = {
  items?: unknown[];
  total?: number | null;
};

type ProfileFormState = {
  full_name: string;
  state: string;
  grad_year: string;
  primary_position: string;
};

const positionOptions = ["LHP", "RHP", "1B", "2B", "SS", "3B", "OF"];

export default function AccountPage() {
  const { loading: authLoading, accessToken, user } = useRequireAuth("/account");

  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [totalEvals, setTotalEvals] = useState(0);
  const [profileForm, setProfileForm] = useState<ProfileFormState>({
    full_name: "",
    state: "",
    grad_year: "",
    primary_position: "",
  });

  useEffect(() => {
    if (!accessToken) return;
    let mounted = true;

    async function loadAccount() {
      setLoading(true);
      setError("");

      try {
        const [accountResp, runsResp] = await Promise.all([
          fetch(`${API_BASE_URL}/account/me`, {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
          }),
          fetch(`${API_BASE_URL}/evaluations?limit=1`, {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
          }),
        ]);

        const data = (await accountResp.json()) as AccountResponse | { detail?: string };
        if (!accountResp.ok) {
          throw new Error(
            typeof data === "object" && data && "detail" in data
              ? data.detail || "Unable to load account."
              : "Unable to load account.",
          );
        }
        if (!mounted) return;
        const typedData = data as AccountResponse;
        setProfileForm({
          full_name: typedData.profile?.full_name || "",
          state: typedData.profile?.state || "",
          grad_year: typedData.profile?.grad_year ? String(typedData.profile.grad_year) : "",
          primary_position: typedData.profile?.primary_position || "",
        });

        if (runsResp.ok) {
          const runsData = (await runsResp.json()) as EvaluationsListResponse;
          const count =
            typeof runsData.total === "number"
              ? runsData.total
              : Array.isArray(runsData.items)
                ? runsData.items.length
                : 0;
          setTotalEvals(count);
        }
      } catch (loadError) {
        if (!mounted) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load account.");
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    }

    loadAccount();

    return () => {
      mounted = false;
    };
  }, [accessToken]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken) return;

    setSavingProfile(true);
    setError("");
    setNotice("");

    const payload: Record<string, unknown> = {};
    if (profileForm.full_name.trim()) payload.full_name = profileForm.full_name.trim();
    if (profileForm.state.trim()) payload.state = profileForm.state.trim().toUpperCase();
    if (profileForm.grad_year.trim()) payload.grad_year = Number(profileForm.grad_year);
    if (profileForm.primary_position.trim()) payload.primary_position = profileForm.primary_position.trim().toUpperCase();

    try {
      const response = await fetch(`${API_BASE_URL}/account/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(payload),
      });
      const data = (await response.json()) as AccountResponse | { detail?: string };
      if (!response.ok) {
        throw new Error(
          typeof data === "object" && data && "detail" in data
            ? data.detail || "Failed to save account profile."
            : "Failed to save account profile.",
        );
      }
      const typedData = data as AccountResponse;
      setProfileForm({
        full_name: typedData.profile?.full_name || "",
        state: typedData.profile?.state || "",
        grad_year: typedData.profile?.grad_year ? String(typedData.profile.grad_year) : "",
        primary_position: typedData.profile?.primary_position || "",
      });
      setNotice("Profile saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save profile.");
    } finally {
      setSavingProfile(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-2xl border border-[var(--cool-stroke)] bg-white p-10 text-center shadow-cool">
          <p className="text-sm text-[var(--cool-ink-muted)]">Loading account...</p>
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
              <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">Account</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight">
                Your account settings.
              </h1>
              <p className="mt-4 text-base text-[var(--cool-ink-muted)] leading-relaxed">
                Manage your profile and view your evaluation history.
              </p>
            </div>
            <Link
              href="/predict"
              className="rounded-full border border-[var(--cool-stroke-strong)] bg-white px-5 py-2.5 text-sm font-semibold text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors"
            >
              Back to evaluate
            </Link>
          </div>

          {(error || notice) && (
            <div
              className={`mt-6 rounded-2xl border p-4 text-sm ${
                error ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-800"
              }`}
            >
              {error || notice}
            </div>
          )}

          <section className="mt-8 grid gap-6 lg:grid-cols-[1.08fr_0.92fr]">
            <form onSubmit={saveProfile} className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-6 shadow-cool">
              <p className="text-[10px] uppercase tracking-[0.28em] text-[var(--cool-ink-muted)] font-semibold">Profile details</p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)] md:col-span-2">
                  Full name
                  <input
                    className="form-control"
                    value={profileForm.full_name}
                    onChange={(event) => setProfileForm((prev) => ({ ...prev, full_name: event.target.value }))}
                    placeholder="Alex Johnson"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
                  State
                  <input
                    className="form-control"
                    maxLength={2}
                    value={profileForm.state}
                    onChange={(event) => setProfileForm((prev) => ({ ...prev, state: event.target.value.toUpperCase() }))}
                    placeholder="CA"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
                  Graduating class
                  <input
                    className="form-control"
                    type="number"
                    min={2000}
                    max={2100}
                    value={profileForm.grad_year}
                    onChange={(event) => setProfileForm((prev) => ({ ...prev, grad_year: event.target.value }))}
                    placeholder="2028"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)] md:col-span-2">
                  Primary position
                  <select
                    className="form-control"
                    value={profileForm.primary_position}
                    onChange={(event) =>
                      setProfileForm((prev) => ({ ...prev, primary_position: event.target.value.toUpperCase() }))
                    }
                  >
                    <option value="">Select position</option>
                    {positionOptions.map((position) => (
                      <option key={position} value={position}>
                        {position}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-[var(--cool-ink-muted)]">Signed in as {user?.email}</p>
                <button
                  type="submit"
                  disabled={savingProfile}
                  className="rounded-full bg-[var(--burnt-sienna)] px-5 py-2.5 text-sm font-semibold text-white shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                >
                  {savingProfile ? "Saving..." : "Save profile"}
                </button>
              </div>
            </form>

            <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-6 shadow-cool">
              <p className="text-[10px] uppercase tracking-[0.28em] text-[var(--cool-ink-muted)] font-semibold">Evaluation history</p>
              <p className="display-font mt-4 text-5xl font-semibold text-[var(--cool-ink)] tracking-tight">{totalEvals}</p>
              <p className="mt-1 text-sm text-[var(--cool-ink-muted)]">
                {totalEvals === 1 ? "evaluation" : "evaluations"} completed
              </p>
              <p className="mt-4 text-sm text-[var(--cool-ink-muted)] leading-relaxed">
                {totalEvals === 0
                  ? "Run your first evaluation to get matched with the best college programs for your profile."
                  : "Run another evaluation anytime — each one is priced per report."}
              </p>
              <Link
                href="/predict"
                className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[var(--burnt-sienna)] hover:underline"
              >
                {totalEvals === 0 ? "Start your first evaluation" : "Run another evaluation"} &rarr;
              </Link>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
