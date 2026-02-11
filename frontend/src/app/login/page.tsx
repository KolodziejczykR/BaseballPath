export default function LoginPage() {
  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto grid max-w-5xl gap-10 md:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Welcome Back</p>
          <h1 className="display-font mt-4 text-4xl md:text-5xl">
            Access your recruiting dashboard.
          </h1>
          <p className="mt-4 text-[var(--muted)]">
            Log in to view your evaluations, save schools, and unlock premium insights.
          </p>
          <div className="mt-8 grid gap-4">
            <div className="glass rounded-2xl p-4">
              <p className="text-sm font-semibold">What you get</p>
              <ul className="mt-2 text-sm text-[var(--muted)]">
                <li>• Saved evaluations and fit history</li>
                <li>• Fast re-runs with new preferences</li>
                <li>• Optional LLM reasoning add-on</li>
              </ul>
            </div>
            <div className="glass rounded-2xl p-4">
              <p className="text-sm font-semibold">New here?</p>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Create an account to start your first evaluation.
              </p>
              <a
                href="/plans"
                className="mt-3 inline-flex rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold text-[var(--navy)]"
              >
                View Plans
              </a>
            </div>
          </div>
        </div>

        <div className="glass shadow-strong rounded-3xl p-8">
          <h2 className="text-xl font-semibold">Sign in</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">Use your email to continue.</p>
          <form className="mt-6 grid gap-4">
            <label className="grid gap-2 text-sm">
              Email
              <input
                type="email"
                placeholder="you@example.com"
                className="rounded-xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm outline-none focus:border-[var(--primary)]"
              />
            </label>
            <label className="grid gap-2 text-sm">
              Password
              <input
                type="password"
                placeholder="••••••••"
                className="rounded-xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm outline-none focus:border-[var(--primary)]"
              />
            </label>
            <button
              type="button"
              className="rounded-full bg-[var(--primary)] px-6 py-3 text-sm font-semibold text-white shadow-strong"
            >
              Continue
            </button>
            <button
              type="button"
              className="rounded-full border border-[var(--stroke)] px-6 py-3 text-sm font-semibold text-[var(--navy)]"
            >
              Sign in with Google
            </button>
            <p className="text-xs text-[var(--muted)]">
              By continuing you agree to our terms.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
