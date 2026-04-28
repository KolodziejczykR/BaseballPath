"use client";

import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DOWN_REASONS = [
  { id: "too_far", label: "Too far" },
  { id: "wrong_level", label: "Wrong level" },
  { id: "cost", label: "Cost" },
  { id: "academic_mismatch", label: "Academic mismatch" },
  { id: "roster_crowded", label: "Roster too crowded" },
  { id: "other", label: "Other" },
];

export type SchoolFeedbackRecord = {
  school_dedupe_key: string;
  is_good_fit: boolean;
  reason: string | null;
};

type Props = {
  accessToken: string;
  evaluationRunId: string;
  schoolDedupeKey: string;
  schoolName: string;
  current: SchoolFeedbackRecord | null;
  onSaved: (record: SchoolFeedbackRecord) => void;
};

export function SchoolFitVote({
  accessToken,
  evaluationRunId,
  schoolDedupeKey,
  schoolName,
  current,
  onSaved,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [showReasons, setShowReasons] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setShowReasons(false);
    setError("");
  }, [schoolDedupeKey]);

  async function submit(isGoodFit: boolean, reason?: string) {
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/feedback/school`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          evaluation_run_id: evaluationRunId,
          school_dedupe_key: schoolDedupeKey,
          school_name: schoolName,
          is_good_fit: isGoodFit,
          reason: reason || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Failed to submit feedback");
      }
      onSaved({
        school_dedupe_key: schoolDedupeKey,
        is_good_fit: data.is_good_fit,
        reason: data.reason ?? null,
      });
      if (!isGoodFit && reason) setShowReasons(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  }

  const voted = current !== null;
  const votedUp = voted && current?.is_good_fit === true;
  const votedDown = voted && current?.is_good_fit === false;

  return (
    <div className="mt-3 rounded-xl border border-[var(--stroke)] bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
        Would this be a good fit for you?
      </p>
      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => {
            setShowReasons(false);
            submit(true);
          }}
          aria-pressed={votedUp}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
            votedUp
              ? "border-[var(--sage-green)] bg-[var(--sage-green)] text-white"
              : "border-[var(--stroke)] bg-white text-[var(--foreground)] hover:border-[var(--sage-green)]"
          } disabled:opacity-50`}
        >
          <span aria-hidden>&#128077;</span>
          <span>Good fit</span>
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => {
            setShowReasons(true);
            if (!votedDown) submit(false);
          }}
          aria-pressed={votedDown}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
            votedDown
              ? "border-[var(--copper)] bg-[var(--copper)] text-white"
              : "border-[var(--stroke)] bg-white text-[var(--foreground)] hover:border-[var(--copper)]"
          } disabled:opacity-50`}
        >
          <span aria-hidden>&#128078;</span>
          <span>Not for me</span>
        </button>
        {voted && (
          <span className="text-xs text-[var(--muted)]">
            {votedUp ? "Saved" : current?.reason ? `Saved: ${formatReason(current.reason)}` : "Saved"}
          </span>
        )}
      </div>

      {showReasons && (
        <div className="mt-3">
          <p className="text-xs text-[var(--muted)]">Why not?</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {DOWN_REASONS.map((r) => {
              const isActive = current?.reason === r.id;
              return (
                <button
                  type="button"
                  key={r.id}
                  disabled={submitting}
                  onClick={() => submit(false, r.id)}
                  className={`rounded-full border px-2.5 py-1 text-xs transition ${
                    isActive
                      ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                      : "border-[var(--stroke)] bg-white text-[var(--muted)] hover:border-[var(--primary)]/50"
                  } disabled:opacity-50`}
                >
                  {r.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
    </div>
  );
}

function formatReason(reason: string): string {
  const found = DOWN_REASONS.find((r) => r.id === reason);
  return found ? found.label : reason;
}
