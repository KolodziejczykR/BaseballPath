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
  const nextPath = searchParams.get("next") || "/dashboard";
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

  async function signInWithGoogle() {
    setSubmitting(true);
    setError("");
    try {
      const redirectTo = `${window.location.origin}${nextPath}`;
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (oauthError) throw oauthError;
    } catch (oauthError) {
      setError(oauthError instanceof Error ? oauthError.message : "Google sign-in failed.");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto grid max-w-5xl gap-10 md:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Welcome Back</p>
          <h1 className="display-font mt-4 text-4xl md:text-5xl">Access your recruiting dashboard.</h1>
          <p className="mt-4 text-[var(--muted)]">
            Log in to view your evaluations, save schools, and unlock premium insights.
          </p>
          <div className="mt-8 grid gap-4">
            <div className="glass rounded-2xl p-4">
              <p className="text-sm font-semibold">What you get</p>
              <ul className="mt-2 text-sm text-[var(--muted)]">
                <li>• Saved evaluations and fit history</li>
                <li>• Plan-based monthly quotas and upgrade path</li>
                <li>• Stripe-powered subscription management</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="glass shadow-strong rounded-3xl p-8">
          <h2 className="text-xl font-semibold">Sign in</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">Use your email to continue.</p>
          <form className="mt-6 grid gap-4" onSubmit={submitEmailPassword}>
            <label className="grid gap-2 text-sm">
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                className="rounded-xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm outline-none focus:border-[var(--primary)]"
                required
              />
            </label>
            <label className="grid gap-2 text-sm">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                className="rounded-xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm outline-none focus:border-[var(--primary)]"
                required
                minLength={8}
              />
            </label>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Please wait..." : "Continue"}
            </button>
            <button
              type="button"
              onClick={signInWithGoogle}
              disabled={submitting}
              className="rounded-full border border-[var(--stroke)] px-6 py-3 text-sm font-semibold text-[var(--navy)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Continue with Google
            </button>

            <p className="text-left text-xs text-[var(--muted)]">
              Need an account?{" "}
              <Link
                href={`/signup?next=${encodeURIComponent(nextPath)}`}
                className="underline underline-offset-2"
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
