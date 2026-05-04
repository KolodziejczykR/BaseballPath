"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useOptionalAuth } from "@/hooks/useOptionalAuth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CheckoutPage() {
  return (
    <Suspense fallback={<div className="min-h-screen px-6 py-16" />}>
      <CheckoutContent />
    </Suspense>
  );
}

function CheckoutContent() {
  const { loading: authLoading, accessToken, isAuthenticated } = useOptionalAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sessionToken, setSessionToken] = useState("");
  const [error, setError] = useState("");
  const initiated = useRef(false);

  // Read session token (localStorage only available client-side)
  useEffect(() => {
    const token = searchParams.get("session_token") || localStorage.getItem("bp_session_token") || "";
    setSessionToken(token);
  }, [searchParams]);

  useEffect(() => {
    if (authLoading || !sessionToken || initiated.current) return;

    // Auth is now required before checkout. Redirect anonymous users to signup.
    if (!isAuthenticated || !accessToken) {
      const next = `/predict/checkout?session_token=${sessionToken}`;
      router.replace(`/signup?session_token=${sessionToken}&next=${encodeURIComponent(next)}`);
      return;
    }

    initiated.current = true;

    async function startCheckout() {
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
          throw new Error(body.detail || "Failed to create checkout session");
        }

        const data = await res.json();
        if (data.checkout_url) {
          window.location.href = data.checkout_url;
        } else {
          throw new Error("No checkout URL returned");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    }

    startCheckout();
  }, [authLoading, accessToken, isAuthenticated, sessionToken, router]);

  if (!sessionToken) {
    return (
      <div className="min-h-screen px-6 py-24">
        <div className="mx-auto max-w-md rounded-2xl border border-red-200 bg-red-50 p-8 text-center shadow-cool">
          <p className="text-sm text-red-700">
            Missing evaluation session. Please{" "}
            <a href="/predict" className="underline font-semibold">start a new evaluation</a>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-24">
      <div className="mx-auto max-w-md rounded-2xl border border-[var(--cool-stroke)] bg-white p-10 text-center shadow-cool space-y-5">
        {error ? (
          <>
            <p className="text-sm text-red-700">{error}</p>
            <a
              href="/predict"
              className="inline-block rounded-full bg-[var(--burnt-sienna)] px-6 py-2.5 text-sm font-semibold !text-white shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-200"
            >
              Start Over
            </a>
          </>
        ) : (
          <>
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--burnt-sienna)] border-t-transparent" />
            <p className="text-sm text-[var(--cool-ink-muted)]">Preparing your checkout...</p>
          </>
        )}
      </div>
    </div>
  );
}
