"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function ClaimResultsContent() {
  const { loading: authLoading, accessToken } = useRequireAuth("/predict/claim-results");
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sessionToken, setSessionToken] = useState("");
  const [purchaseId, setPurchaseId] = useState("");
  const [runId, setRunId] = useState("");
  const [error, setError] = useState("");
  const initiated = useRef(false);

  // Read params (localStorage only available client-side)
  useEffect(() => {
    setSessionToken(searchParams.get("session_token") || localStorage.getItem("bp_session_token") || "");
    setPurchaseId(searchParams.get("purchase_id") || localStorage.getItem("bp_purchase_id") || "");
    setRunId(searchParams.get("run_id") || "");
  }, [searchParams]);

  useEffect(() => {
    if (authLoading || !accessToken || !sessionToken || initiated.current) return;
    initiated.current = true;

    async function claimAndRedirect() {
      try {
        const res = await fetch(`${API}/evaluate/claim`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            session_token: sessionToken,
            purchase_id: purchaseId || undefined,
          }),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          // 403 = already claimed by another user; 404 = expired
          throw new Error(body.detail || "Failed to claim evaluation");
        }

        // Clean up localStorage
        localStorage.removeItem("bp_session_token");
        localStorage.removeItem("bp_purchase_id");

        // Redirect to the full evaluation detail page
        if (runId) {
          router.replace(`/evaluations/${runId}`);
        } else {
          router.replace("/predict");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    }

    claimAndRedirect();
  }, [authLoading, accessToken, sessionToken, purchaseId, runId, router]);

  if (error) {
    return (
      <div className="min-h-screen px-6 py-24">
        <div className="mx-auto max-w-md rounded-2xl border border-red-200 bg-red-50 p-8 text-center space-y-4 shadow-cool">
          <p className="text-sm text-red-700">{error}</p>
          <a
            href="/predict"
            className="inline-block rounded-full bg-[var(--burnt-sienna)] px-6 py-2.5 text-sm font-semibold !text-white shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-200"
          >
            Start New Evaluation
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-24">
      <div className="mx-auto max-w-md rounded-2xl border border-[var(--cool-stroke)] bg-white p-10 text-center space-y-5 shadow-cool">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--burnt-sienna)] border-t-transparent" />
        <p className="text-sm font-medium text-[var(--cool-ink)]">Saving your results to your account...</p>
      </div>
    </div>
  );
}

export default function ClaimResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen px-6 py-24">
          <div className="mx-auto max-w-md rounded-2xl border border-[var(--cool-stroke)] bg-white p-10 text-center space-y-5 shadow-cool">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--burnt-sienna)] border-t-transparent" />
            <p className="text-sm text-[var(--cool-ink-muted)]">Loading...</p>
          </div>
        </div>
      }
    >
      <ClaimResultsContent />
    </Suspense>
  );
}
