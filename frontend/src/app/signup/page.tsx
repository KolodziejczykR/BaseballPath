"use client";

import Link from "next/link";
import { type FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-screen px-6 py-16" />}>
      <SignupContent />
    </Suspense>
  );
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Inlined to keep the signup bundle small — us-states-data.ts is ~29 KB of
// SVG path data we don't need here, just the abbreviations.
const US_STATE_CODES = new Set([
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
  "DC",
]);

function SignupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionToken = searchParams.get("session_token") || "";
  const defaultNext = sessionToken
    ? `/predict/checkout?session_token=${sessionToken}`
    : "/predict";
  const nextPath = searchParams.get("next") || defaultNext;
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);

  const [fullName, setFullName] = useState("");
  const [stateAbbr, setStateAbbr] = useState("");
  const [gradYear, setGradYear] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [infoMessage, setInfoMessage] = useState("");

  // Push state + grad_year into the account profile right after signup so the
  // /account form is pre-populated (mirrors the PATCH /account/me call that
  // page makes manually). Non-fatal — user can fill them on /account if this
  // request fails.
  async function syncProfileFields(accessToken: string) {
    const payload: Record<string, unknown> = {};
    if (stateAbbr.trim()) payload.state = stateAbbr.trim().toUpperCase();
    if (gradYear.trim()) payload.grad_year = Number(gradYear);
    if (Object.keys(payload).length === 0) return;
    try {
      await fetch(`${API}/account/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(payload),
      });
    } catch {
      // Swallow — profile can be edited later on /account.
    }
  }

  async function routeAfterSession(accessToken: string) {
    if (!sessionToken) {
      router.replace(nextPath);
      return;
    }
    try {
      const res = await fetch(`${API}/billing/create-eval-checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ session_token: sessionToken }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Failed to start checkout");
      }
      const payload = await res.json();
      if (payload?.checkout_url) {
        window.location.href = payload.checkout_url as string;
        return;
      }
      throw new Error("Checkout URL missing from response");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start checkout");
      router.replace(nextPath);
    }
  }

  useEffect(() => {
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      if (data.session?.access_token) {
        void routeAfterSession(data.session.access_token);
      }
    });
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextPath, router, supabase, sessionToken]);

  async function submitSignup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setInfoMessage("");

    const trimmedState = stateAbbr.trim().toUpperCase();
    if (!trimmedState) {
      setError("Please enter your state — we use this to show in-state vs out-of-state tuition correctly.");
      setSubmitting(false);
      return;
    }
    if (!US_STATE_CODES.has(trimmedState)) {
      setError("Please enter a valid 2-letter US state abbreviation (e.g., CA, NY, TX).");
      setSubmitting(false);
      return;
    }

    try {
      const meta: Record<string, string | number> = {};
      if (fullName.trim()) meta.full_name = fullName.trim();
      if (trimmedState) meta.state = trimmedState;
      if (gradYear.trim()) meta.grad_year = Number(gradYear);

      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: Object.keys(meta).length > 0 ? meta : undefined,
          emailRedirectTo: `${window.location.origin}${nextPath}`
        },
      });

      if (signUpError) {
        // Supabase returns explicit "already registered" errors when email
        // confirmation is OFF — surface a friendlier message and keep the
        // same wording as the silent-duplicate branch below.
        const message = signUpError.message?.toLowerCase() || "";
        if (message.includes("already") || message.includes("registered")) {
          throw new Error("An account with this email already exists. Please sign in below.");
        }
        throw signUpError;
      }

      // When email confirmation is ON, supabase silently returns success with
      // an empty `identities` array if the email is already registered (so it
      // doesn't leak account existence to attackers). We DO want to tell our
      // own user, so detect that shape and surface a real error.
      if (data.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
        throw new Error("An account with this email already exists. Please sign in below.");
      }

      if (data.session?.access_token) {
        await syncProfileFields(data.session.access_token);
        await routeAfterSession(data.session.access_token);
        return;
      }

      setInfoMessage("Account created. Check your email to verify your address, then sign in.");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-up failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-16 md:py-24">
      <div className="mx-auto grid max-w-5xl gap-12 md:grid-cols-[1.1fr_0.9fr] items-start">
        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">Create Your Account</p>
          <h1 className="display-font mt-5 text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight">
            Start your recruiting workspace.
          </h1>
          <p className="mt-5 text-base text-[var(--cool-ink-muted)] leading-relaxed">
            {sessionToken
              ? "Create your account to unlock your full evaluation. You'll be taken straight to checkout."
              : "Create an account to save your evaluations and revisit them anytime."}
          </p>
          <div className="mt-8">
            <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-5 shadow-cool">
              <p className="text-sm font-semibold text-[var(--cool-ink)]">Your account includes</p>
              <ul className="mt-3 space-y-2 text-sm text-[var(--cool-ink-muted)]">
                <li>• Save and revisit every evaluation you run</li>
                <li>• Pay per evaluation — no subscription</li>
                <li>• Deep roster and recruiting research on each match</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white shadow-cool-strong p-8">
          <h2 className="display-font text-2xl font-semibold text-[var(--cool-ink)] tracking-tight">Create account</h2>
          <p className="mt-2 text-sm text-[var(--cool-ink-muted)]">Pay per evaluation — no subscription.</p>
          <form className="mt-6 grid gap-4" onSubmit={submitSignup}>
            <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
              Full name
              <input
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Alex Johnson"
                className="form-control"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
                State <span className="text-[var(--burnt-sienna)]">*</span>
                <input
                  type="text"
                  value={stateAbbr}
                  onChange={(event) => setStateAbbr(event.target.value.toUpperCase())}
                  placeholder="CA"
                  maxLength={2}
                  required
                  className="form-control uppercase"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
                Graduating class
                <select
                  value={gradYear}
                  onChange={(event) => setGradYear(event.target.value)}
                  className="form-control"
                >
                  <option value="">Select year</option>
                  <option value="2026">2026</option>
                  <option value="2027">2027</option>
                  <option value="2028">2028</option>
                  <option value="2029">2029</option>
                  <option value="2030">2030</option>
                  <option value="2031">2031+</option>
                </select>
              </label>
            </div>
            <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                className="form-control"
                required
              />
            </label>
            <label className="grid gap-2 text-sm font-medium text-[var(--cool-ink)]">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                className="form-control"
                required
                minLength={8}
              />
            </label>

            {error && <p className="text-sm text-red-600">{error}</p>}
            {infoMessage && <p className="text-sm text-[var(--sage-green)]">{infoMessage}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="rounded-full bg-[var(--burnt-sienna)] px-6 py-3 text-sm font-semibold text-white shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
            >
              {submitting ? "Please wait..." : "Create Account"}
            </button>

            <p className="text-left text-xs text-[var(--cool-ink-muted)]">
              Already have an account?{" "}
              <Link
                href={`/login?next=${encodeURIComponent(nextPath)}`}
                className="font-semibold text-[var(--cool-ink)] underline underline-offset-2 hover:text-[var(--burnt-sienna)] transition-colors"
              >
                Sign in
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
