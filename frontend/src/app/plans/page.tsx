"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";
import { AuthenticatedTopBar } from "@/components/ui/authenticated-topbar";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const plans = [
  {
    key: "starter",
    name: "Starter",
    price: "$0",
    desc: "Get your baseline fit report.",
    features: ["Division projection", "School matching", "Basic playing time"],
  },
  {
    key: "pro",
    name: "Pro",
    price: "$29",
    desc: "More depth and faster insights.",
    features: ["Expanded filters", "Enhanced ranking", "Priority processing"],
    highlight: true,
  },
  {
    key: "elite",
    name: "Elite",
    price: "$59",
    desc: "Full suite and premium reasoning.",
    features: ["LLM fit narratives", "Advanced analytics", "Coach-ready exports"],
  },
];

export default function PlansPage() {
  const router = useRouter();
  const supabase = useMemo(() => getSupabaseBrowserClient(), []);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [currentPlan, setCurrentPlan] = useState<string>("starter");
  const [loadingPlan, setLoadingPlan] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function loadCurrentPlan() {
      setLoadingPlan(true);
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token ?? null;
      const email = data.session?.user?.email ?? null;
      if (!mounted) return;
      setAccessToken(token);
      setUserEmail(email);

      if (!token) {
        setCurrentPlan("starter");
        setLoadingPlan(false);
        return;
      }

      try {
        const accountResponse = await fetch(`${API_BASE_URL}/account/me`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        });
        const accountData = (await accountResponse.json()) as { plan?: { tier?: string }; detail?: string };
        if (accountResponse.ok) {
          setCurrentPlan(accountData.plan?.tier || "starter");
        }
      } finally {
        if (mounted) {
          setLoadingPlan(false);
        }
      }
    }

    loadCurrentPlan();
    return () => {
      mounted = false;
    };
  }, [supabase]);

  async function beginCheckout(planTier: string) {
    if (planTier === "starter") return;

    setError("");
    if (!accessToken) {
      router.push("/login?next=/plans");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/billing/create-checkout-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          plan_tier: planTier,
        }),
      });
      const data = (await response.json()) as { checkout_url?: string; detail?: string };
      if (!response.ok || !data.checkout_url) {
        throw new Error(data.detail || "Unable to start Stripe checkout.");
      }
      window.location.href = data.checkout_url;
    } catch (checkoutError) {
      setError(checkoutError instanceof Error ? checkoutError.message : "Checkout failed.");
      setSubmitting(false);
    }
  }

  async function openBillingPortal() {
    if (!accessToken) {
      router.push("/login?next=/plans");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/billing/create-portal-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      const data = (await response.json()) as { portal_url?: string; detail?: string };
      if (!response.ok || !data.portal_url) {
        throw new Error(data.detail || "Unable to open billing portal.");
      }
      window.location.href = data.portal_url;
    } catch (portalError) {
      setError(portalError instanceof Error ? portalError.message : "Unable to open billing portal.");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen">
      {accessToken && <AuthenticatedTopBar accessToken={accessToken} userEmail={userEmail} />}

      <main className="px-6 py-10 md:py-12">
        <div className="mx-auto max-w-6xl">
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Plans</p>
          <h1 className="display-font mt-4 text-4xl md:text-5xl">Choose the level of insight you need.</h1>
          <p className="mt-4 text-[var(--muted)]">
            Pricing is placeholder for now. Each plan unlocks a different depth of analysis.
          </p>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Current plan:{" "}
            <span className="font-semibold text-[var(--navy)]">{loadingPlan ? "Loading..." : currentPlan.toUpperCase()}</span>
          </p>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-3xl border p-8 shadow-soft ${
                  plan.highlight ? "border-[var(--primary)] bg-white shadow-strong" : "border-[var(--stroke)] bg-white/70"
                }`}
              >
                <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">{plan.name}</p>
                <p className="mt-3 text-3xl font-semibold">{plan.price}</p>
                <p className="mt-2 text-sm text-[var(--muted)]">{plan.desc}</p>
                <ul className="mt-6 space-y-2 text-sm text-[var(--muted)]">
                  {plan.features.map((feature) => (
                    <li key={feature}>• {feature}</li>
                  ))}
                </ul>
                {plan.key === currentPlan ? (
                  <button
                    disabled
                    className="mt-8 w-full cursor-not-allowed rounded-full border border-[var(--stroke)] bg-[var(--sand)] px-5 py-3 text-sm font-semibold text-[var(--navy)] opacity-70"
                  >
                    Current Plan
                  </button>
                ) : (
                  <button
                    disabled={submitting}
                    onClick={() => beginCheckout(plan.key)}
                    className={`mt-8 w-full rounded-full px-5 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${
                      plan.highlight ? "bg-[var(--primary)] text-white" : "border border-[var(--stroke)] text-[var(--navy)]"
                    }`}
                  >
                    {plan.key === "starter" ? "Starter Included" : "Select Plan"}
                  </button>
                )}
              </div>
            ))}
          </div>

          {currentPlan !== "starter" && (
            <button
              onClick={openBillingPortal}
              disabled={submitting}
              className="mt-8 rounded-full border border-[var(--stroke)] bg-white px-5 py-3 text-sm font-semibold text-[var(--navy)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Manage Billing in Stripe
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
