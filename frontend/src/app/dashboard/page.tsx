export default function DashboardPage() {
  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Dashboard</p>
            <h1 className="display-font mt-4 text-4xl md:text-5xl">
              Your recruiting command center.
            </h1>
            <p className="mt-3 text-[var(--muted)]">
              Launch new evaluations, track results, and unlock premium insights.
            </p>
          </div>
          <a
            href="/predict"
            className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong"
          >
            Start New Evaluation
          </a>
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <div className="glass rounded-2xl p-6 shadow-soft">
            <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Last run</p>
            <p className="mt-3 text-xl font-semibold">No evaluations yet</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Start your first evaluation to see school matches here.
            </p>
          </div>
          <div className="glass rounded-2xl p-6 shadow-soft">
            <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Plan status</p>
            <p className="mt-3 text-xl font-semibold">Starter (placeholder)</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Upgrade to unlock LLM fit narratives and advanced analytics.
            </p>
            <a
              href="/plans"
              className="mt-4 inline-flex rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold text-[var(--navy)]"
            >
              View Plans
            </a>
          </div>
          <div className="glass rounded-2xl p-6 shadow-soft">
            <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Saved schools</p>
            <p className="mt-3 text-xl font-semibold">0 saved</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Save schools as you review matches.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
