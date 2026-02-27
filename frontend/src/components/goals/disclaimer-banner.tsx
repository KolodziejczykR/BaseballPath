"use client";

export function DisclaimerBanner() {
  return (
    <div className="rounded-xl border border-[var(--stroke)] bg-[var(--sand)]/30 p-4">
      <p className="text-xs text-[var(--muted)]">
        Model estimates are based on patterns in historical player data. They reflect statistical tendencies, not
        guarantees. Many factors beyond metrics including academics, character, coaching relationships, and timing
        affect recruiting outcomes. Use these insights as one tool in your development plan.
      </p>
    </div>
  );
}
