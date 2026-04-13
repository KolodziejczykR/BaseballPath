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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [infoMessage, setInfoMessage] = useState("");

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

    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: fullName.trim() ? { full_name: fullName.trim() } : undefined,
          emailRedirectTo: `${window.location.origin}${nextPath}`
        },
      });

      if (signUpError) throw signUpError;
      if (data.session?.access_token) {
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

  async function signUpWithGoogle() {
    setSubmitting(true);
    setError("");
    setInfoMessage("");
    try {
      const redirectTo = `${window.location.origin}${nextPath}`;
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (oauthError) throw oauthError;
    } catch (oauthError) {
      setError(oauthError instanceof Error ? oauthError.message : "Google sign-up failed.");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto grid max-w-5xl gap-10 md:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Create Your Account</p>
          <h1 className="display-font mt-4 text-4xl md:text-5xl">Start your recruiting workspace.</h1>
          <p className="mt-4 pl-1 text-[var(--muted)]">
            {sessionToken
              ? "Create your account to unlock your full evaluation. You'll be taken straight to checkout."
              : "Create an account to save your evaluations and revisit them anytime."}
          </p>
          <div className="mt-8 grid gap-4">
            <div className="glass rounded-2xl p-4">
              <p className="text-sm font-semibold">Your account includes</p>
              <ul className="mt-2 text-sm text-[var(--muted)]">
                <li>• Save and revisit every evaluation you run</li>
                <li>• Pay per evaluation — no subscription</li>
                <li>• Deep roster and recruiting research on each match</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="glass shadow-strong rounded-3xl p-8">
          <h2 className="text-xl font-semibold">Create account</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">Pay per evaluation — no subscription.</p>
          <form className="mt-6 grid gap-4" onSubmit={submitSignup}>
            <label className="grid gap-2 text-sm">
              Full name
              <input
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Alex Johnson"
                className="rounded-xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm outline-none focus:border-[var(--primary)]"
              />
            </label>
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
            {infoMessage && <p className="text-sm text-[var(--accent)]">{infoMessage}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Please wait..." : "Create Account"}
            </button>
            <button
              type="button"
              onClick={signUpWithGoogle}
              disabled={submitting}
              className="rounded-full border border-[var(--stroke)] px-6 py-3 text-sm font-semibold text-[var(--navy)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Continue with Google
            </button>

            <p className="text-left text-xs text-[var(--muted)]">
              Already have an account?{" "}
              <Link
                href={`/login?next=${encodeURIComponent(nextPath)}`}
                className="underline underline-offset-2"
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
