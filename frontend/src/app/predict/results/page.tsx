"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useOptionalAuth } from "@/hooks/useOptionalAuth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_RETRIES = 2;
const RETRY_DELAYS = [1500, 3000];

type FinalizeResult = {
  run_id: string;
};

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen px-6 py-16" />}>
      <ResultsContent />
    </Suspense>
  );
}

function ResultsContent() {
  const { loading: authLoading, accessToken, isAuthenticated } = useOptionalAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [purchaseId, setPurchaseId] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [status, setStatus] = useState("Confirming your payment...");
  const [error, setError] = useState("");
  const initiated = useRef(false);

  useEffect(() => {
    setPurchaseId(searchParams.get("purchase_id") || "");
    setSessionToken(searchParams.get("session_token") || localStorage.getItem("bp_session_token") || "");
  }, [searchParams]);

  useEffect(() => {
    if (authLoading || !purchaseId || !sessionToken || initiated.current) return;

    // Auth is required before payment, so the user must be signed in to
    // finalize. If they land here anonymous, bounce them to login.
    if (!isAuthenticated || !accessToken) {
      const next = `/predict/results?purchase_id=${purchaseId}&session_token=${sessionToken}`;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
      return;
    }

    initiated.current = true;

    async function finalize(attempt: number): Promise<void> {
      try {
        const res = await fetch(`${API}/evaluations/finalize`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            session_token: sessionToken,
            purchase_id: purchaseId,
          }),
        });

        if (res.status === 402 && attempt < MAX_RETRIES) {
          setStatus(`Waiting for payment confirmation... (${attempt + 1}/${MAX_RETRIES})`);
          await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]));
          return finalize(attempt + 1);
        }

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "Failed to finalize evaluation");
        }

        const data = (await res.json()) as FinalizeResult;

        localStorage.removeItem("bp_session_token");
        localStorage.removeItem("bp_purchase_id");
        router.replace(`/evaluations/${data.run_id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    }

    setStatus("Generating your personalized evaluation...");
    finalize(0);
  }, [authLoading, accessToken, isAuthenticated, purchaseId, sessionToken, router]);

  if (!purchaseId || !sessionToken) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-md rounded-3xl border border-red-300 bg-red-50 p-8 text-center">
          <p className="text-sm text-red-700">
            Missing payment or session information. Please{" "}
            <a href="/predict" className="underline">start a new evaluation</a>.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen px-6 py-16">
        <div className="mx-auto max-w-md rounded-3xl border border-red-300 bg-red-50 p-8 text-center space-y-4">
          <p className="text-sm text-red-700">{error}</p>
          <a
            href="/predict"
            className="inline-block rounded-full bg-[var(--primary)] px-6 py-2.5 text-sm font-semibold !text-white"
          >
            Start Over
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-md rounded-3xl border border-[var(--stroke)] bg-white/80 p-8 text-center space-y-4">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
        <p className="text-sm text-[var(--muted)]">{status}</p>
        <p className="text-xs text-[var(--muted)]">
          This may take a moment while we generate AI-personalized insights for your schools.
        </p>
      </div>
    </div>
  );
}
