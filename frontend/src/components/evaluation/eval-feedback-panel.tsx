"use client";

import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LEVEL_OPTIONS: { id: "too_low" | "just_right" | "too_high"; label: string }[] = [
  { id: "too_low", label: "Too low" },
  { id: "just_right", label: "Just right" },
  { id: "too_high", label: "Too high" },
];

const DISCOVERY_OPTIONS: { id: "yes" | "some" | "no"; label: string }[] = [
  { id: "yes", label: "Yes" },
  { id: "some", label: "Some" },
  { id: "no", label: "No" },
];

type Props = {
  accessToken: string;
  evaluationRunId: string;
  defaultName?: string | null;
  onDismiss: () => void;
};

export function EvalFeedbackPanel({
  accessToken,
  evaluationRunId,
  defaultName,
  onDismiss,
}: Props) {
  const [level, setLevel] = useState<"too_low" | "just_right" | "too_high" | null>(null);
  const [matchQuality, setMatchQuality] = useState<number | null>(null);
  const [discovery, setDiscovery] = useState<"yes" | "some" | "no" | null>(null);
  const [improvement, setImprovement] = useState("");
  const [praise, setPraise] = useState("");
  const [quoteConsent, setQuoteConsent] = useState(false);
  const [displayName, setDisplayName] = useState(defaultName || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  async function dismissPermanently() {
    try {
      await fetch(`${API_BASE_URL}/feedback/run/dismiss`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ evaluation_run_id: evaluationRunId }),
      });
    } catch {
      // Best-effort — close regardless.
    }
    onDismiss();
  }

  async function submit() {
    if (submitting) return;
    if (matchQuality == null) {
      setError("Please rate how well this matched your preferences.");
      return;
    }
    if (quoteConsent && !displayName.trim()) {
      setError("Please add a name to attribute your quote.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/feedback/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          evaluation_run_id: evaluationRunId,
          level_rating: level,
          match_quality: matchQuality,
          discovery,
          improvement: improvement.trim() || null,
          praise: praise.trim() || null,
          quote_consent: quoteConsent,
          display_name: quoteConsent ? displayName.trim() : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Failed to submit feedback");
      }
      setSubmitted(true);
      setTimeout(onDismiss, 1800);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mt-6">
      <div className="rounded-3xl border border-[var(--stroke)] bg-[var(--background)] p-6 shadow-soft md:p-8">
        {submitted ? (
          <div className="py-6 text-center">
            <p className="display-font text-2xl text-[var(--foreground)]">Thank you!</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Your feedback helps us improve every evaluation.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">
                  Quick feedback
                </p>
                <h2 className="display-font mt-2 text-2xl text-[var(--foreground)]">
                  How did your evaluation do?
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  You&apos;re an early user — your honest take shapes what we build next.
                </p>
              </div>
              <button
                type="button"
                onClick={onDismiss}
                aria-label="Hide feedback"
                className="shrink-0 rounded-full p-1 text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                &times;
              </button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              {/* Level */}
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  Did the level of schools feel right?
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {LEVEL_OPTIONS.map((opt) => {
                    const active = level === opt.id;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setLevel(opt.id)}
                        className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                          active
                            ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                            : "border-[var(--stroke)] bg-white text-[var(--foreground)] hover:border-[var(--primary)]/40"
                        }`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Match quality */}
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  How well did this match your preferences?{" "}
                  <span className="text-[var(--copper)]">*</span>
                </p>
                <div className="mt-2 flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map((n) => {
                    const active = matchQuality === n;
                    return (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setMatchQuality(n)}
                        aria-label={`${n} out of 5`}
                        className={`flex h-9 w-9 items-center justify-center rounded-full border text-sm font-semibold transition ${
                          active
                            ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                            : "border-[var(--stroke)] bg-white text-[var(--foreground)] hover:border-[var(--primary)]/40"
                        }`}
                      >
                        {n}
                      </button>
                    );
                  })}
                  <span className="ml-1 text-xs text-[var(--muted)]">
                    (1 = poor, 5 = excellent)
                  </span>
                </div>
              </div>

              {/* Discovery */}
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  Did you discover schools you hadn&apos;t considered?
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {DISCOVERY_OPTIONS.map((opt) => {
                    const active = discovery === opt.id;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setDiscovery(opt.id)}
                        className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                          active
                            ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                            : "border-[var(--stroke)] bg-white text-[var(--foreground)] hover:border-[var(--primary)]/40"
                        }`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quote consent */}
              <div className="rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
                <label className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                  <input
                    type="checkbox"
                    checked={quoteConsent}
                    onChange={(e) => setQuoteConsent(e.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    BaseballPath can use my feedback publically for marketing purposes (anonymously or with attribution).
                  </span>
                </label>
                {quoteConsent && (
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Name to attribute (e.g., 'Alex R., 2027 OF')"
                    className="form-control mt-3 text-sm"
                  />
                )}
              </div>

              {/* Improvement */}
              <div className="lg:col-span-2">
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  What&apos;s one thing we could improve?
                </p>
                <textarea
                  value={improvement}
                  onChange={(e) => setImprovement(e.target.value)}
                  placeholder="Anything you wish was different..."
                  className="form-control mt-2 min-h-[72px] resize-y text-sm"
                />
              </div>

              {/* Praise */}
              <div className="lg:col-span-2">
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  Anything we did especially well?
                </p>
                <textarea
                  value={praise}
                  onChange={(e) => setPraise(e.target.value)}
                  placeholder="What stood out, surprised you, or was useful..."
                  className="form-control mt-2 min-h-[72px] resize-y text-sm"
                />
              </div>
            </div>

            {error && (
              <p className="mt-4 rounded-xl border border-red-300 bg-red-50 p-3 text-xs text-red-700">
                {error}
              </p>
            )}

            <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={dismissPermanently}
                className="text-xs font-semibold text-[var(--muted)] hover:underline"
              >
                Don&apos;t ask again
              </button>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={onDismiss}
                  className="rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold text-[var(--foreground)]"
                >
                  Maybe later
                </button>
                <button
                  type="button"
                  onClick={submit}
                  disabled={submitting}
                  className="rounded-full bg-[var(--primary)] px-5 py-2 text-xs font-semibold !text-white shadow-soft disabled:opacity-50"
                >
                  {submitting ? "Sending..." : "Send feedback"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
