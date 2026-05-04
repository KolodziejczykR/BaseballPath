"use client";

import Link from "next/link";
import { type FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen px-6 py-16" />}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/predict";
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      if (data.session) {
        router.replace(nextPath);
      }
    });
    return () => {
      mounted = false;
    };
  }, [nextPath, router, supabase]);

  async function submitEmailPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (signInError) throw signInError;
      router.replace(nextPath);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-16 md:py-24">
      <div className="mx-auto grid max-w-5xl gap-12 md:grid-cols-[1.1fr_0.9fr] items-start">
        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">Welcome Back</p>
          <h1 className="display-font mt-5 text-4xl md:text-5xl text-[var(--cool-ink)] font-semibold tracking-tight leading-tight">
            Access your recruiting dashboard.
          </h1>
          <p className="mt-5 text-base text-[var(--cool-ink-muted)] leading-relaxed">
            Log in to view your evaluations, save schools, and unlock premium insights.
          </p>
          <div className="mt-8">
            <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-5 shadow-cool">
              <p className="text-sm font-semibold text-[var(--cool-ink)]">What you get</p>
              <ul className="mt-3 space-y-2 text-sm text-[var(--cool-ink-muted)]">
                <li>• Saved evaluations and fit history</li>
                <li>• Pay per evaluation — no subscription</li>
                <li>• Deep roster and recruiting research on each match</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white shadow-cool-strong p-8">
          <h2 className="display-font text-2xl font-semibold text-[var(--cool-ink)] tracking-tight">Sign in</h2>
          <p className="mt-2 text-sm text-[var(--cool-ink-muted)]">Use your email to continue.</p>
          <form className="mt-6 grid gap-4" onSubmit={submitEmailPassword}>
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

            <button
              type="submit"
              disabled={submitting}
              className="rounded-full bg-[var(--burnt-sienna)] px-6 py-3 text-sm font-semibold text-white shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
            >
              {submitting ? "Please wait..." : "Continue"}
            </button>

            <p className="text-left text-xs text-[var(--cool-ink-muted)]">
              Need an account?{" "}
              <Link
                href={`/signup?next=${encodeURIComponent(nextPath)}`}
                className="font-semibold text-[var(--cool-ink)] underline underline-offset-2 hover:text-[var(--burnt-sienna)] transition-colors"
              >
                Create one
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
