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
  plan?: {
    tier?: string;
    status?: string;
    remaining_evals?: number | null;
    monthly_eval_limit?: number | null;
    llm_enabled?: boolean;
  };
  usage?: {
    period_start?: string;
    eval_count?: number;
  };
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
  const [account, setAccount] = useState<AccountResponse | null>(null);
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
        const response = await fetch(`${API_BASE_URL}/account/me`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
        const data = (await response.json()) as AccountResponse | { detail?: string };
        if (!response.ok) {
          throw new Error(
            typeof data === "object" && data && "detail" in data
              ? data.detail || "Unable to load account."
              : "Unable to load account.",
          );
        }
        if (!mounted) return;
        const typedData = data as AccountResponse;
        setAccount(typedData);
        setProfileForm({
          full_name: typedData.profile?.full_name || "",
          state: typedData.profile?.state || "",
          grad_year: typedData.profile?.grad_year ? String(typedData.profile.grad_year) : "",
          primary_position: typedData.profile?.primary_position || "",
        });
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
      setAccount(typedData);
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
        <div className="mx-auto max-w-3xl rounded-3xl border border-[var(--stroke)] bg-white/80 p-10 text-center">
          <p className="text-sm text-[var(--muted)]">Loading account...</p>
        </div>
      </div>
    );
  }

  const totalEvals = account?.usage?.eval_count ?? 0;

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={user?.email} />}

      <main className="px-6 pt-5 pb-10 md:pt-6 md:pb-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Account</p>
              <h1 className="display-font mt-3 text-4xl md:text-5xl">Your account settings.</h1>
              <p className="mt-3 max-w-none pl-1 text-[var(--muted)]">
                Manage your profile and view your evaluation history.
              </p>
            </div>
            <Link
              href="/predict"
              className="rounded-full border border-[var(--stroke)] bg-white/80 px-5 py-2.5 text-sm font-semibold text-[var(--navy)]"
            >
              Back to evaluate
            </Link>
          </div>

          {(error || notice) && (
            <div
              className={`mt-6 rounded-2xl border p-4 text-sm ${
                error ? "border-red-300 bg-red-50 text-red-700" : "border-emerald-300 bg-emerald-50 text-emerald-800"
              }`}
            >
              {error || notice}
            </div>
          )}

          <section className="mt-8 grid gap-6 lg:grid-cols-[1.08fr_0.92fr]">
            <form onSubmit={saveProfile} className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Profile details</p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium md:col-span-2">
                  Full name
                  <input
                    className="form-control"
                    value={profileForm.full_name}
                    onChange={(event) => setProfileForm((prev) => ({ ...prev, full_name: event.target.value }))}
                    placeholder="Alex Johnson"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium">
                  State
                  <input
                    className="form-control"
                    maxLength={2}
                    value={profileForm.state}
                    onChange={(event) => setProfileForm((prev) => ({ ...prev, state: event.target.value.toUpperCase() }))}
                    placeholder="CA"
                  />
                </label>
                <label className="grid gap-2 text-sm font-medium">
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
                <label className="grid gap-2 text-sm font-medium md:col-span-2">
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
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-[var(--muted)]">Signed in as {user?.email}</p>
                <button
                  type="submit"
                  disabled={savingProfile}
                  className="rounded-full bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingProfile ? "Saving..." : "Save profile"}
                </button>
              </div>
            </form>

            <div className="glass rounded-2xl p-6 shadow-soft">
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Evaluation history</p>
              <p className="mt-3 text-3xl font-semibold text-[var(--navy)]">{totalEvals}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {totalEvals === 1 ? "evaluation" : "evaluations"} completed
              </p>
              <p className="mt-4 text-sm text-[var(--muted)]">
                {totalEvals === 0
                  ? "Run your first evaluation to get matched with the best college programs for your profile."
                  : "Next evaluation: $29 per report."}
              </p>
              <Link href="/predict" className="mt-5 inline-flex text-sm font-semibold text-[var(--primary)]">
                {totalEvals === 0 ? "Start your first evaluation" : "Run another evaluation"}
              </Link>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
