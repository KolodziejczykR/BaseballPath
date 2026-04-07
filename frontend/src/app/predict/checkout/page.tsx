"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useOptionalAuth } from "@/hooks/useOptionalAuth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CheckoutPage() {
  const { loading: authLoading, accessToken, isAuthenticated } = useOptionalAuth();
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
    initiated.current = true;

    async function startCheckout() {
      try {
        // If authenticated, claim the pending evaluation for this user
        if (isAuthenticated && accessToken) {
          await fetch(`${API}/evaluate/claim`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
            body: JSON.stringify({ session_token: sessionToken }),
          });
        }

        // Create Stripe checkout session (auth optional)
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (accessToken) {
          headers["Authorization"] = `Bearer ${accessToken}`;
        }

        const res = await fetch(`${API}/billing/create-eval-checkout`, {
          method: "POST",
          headers,
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
  }, [authLoading, accessToken, isAuthenticated, sessionToken]);

  if (!sessionToken) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-md rounded-3xl border border-red-300 bg-red-50 p-8 text-center">
          <p className="text-sm text-red-700">
            Missing evaluation session. Please{" "}
            <a href="/predict" className="underline">start a new evaluation</a>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-md rounded-3xl border border-[var(--stroke)] bg-white/80 p-8 text-center space-y-4">
        {error ? (
          <>
            <p className="text-sm text-red-700">{error}</p>
            <a
              href="/predict"
              className="inline-block rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold !text-white"
            >
              Start Over
            </a>
          </>
        ) : (
          <>
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
            <p className="text-sm text-[var(--muted)]">Preparing your checkout...</p>
          </>
        )}
      </div>
    </div>
  );
}
