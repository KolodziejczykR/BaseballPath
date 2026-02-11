const plans = [
  {
    name: "Starter",
    price: "$0",
    desc: "Get your baseline fit report.",
    features: ["Division projection", "School matching", "Basic playing time"],
  },
  {
    name: "Pro",
    price: "$29",
    desc: "More depth and faster insights.",
    features: ["Expanded filters", "Enhanced ranking", "Priority processing"],
    highlight: true,
  },
  {
    name: "Elite",
    price: "$59",
    desc: "Full suite and premium reasoning.",
    features: ["LLM fit narratives", "Advanced analytics", "Coach-ready exports"],
  },
];

export default function PlansPage() {
  return (
    <div className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Plans</p>
        <h1 className="display-font mt-4 text-4xl md:text-5xl">
          Choose the level of insight you need.
        </h1>
        <p className="mt-4 text-[var(--muted)]">
          Pricing is placeholder for now. Each plan unlocks a different depth of analysis.
        </p>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-3xl border p-8 shadow-soft ${
                plan.highlight
                  ? "border-[var(--primary)] bg-white shadow-strong"
                  : "border-[var(--stroke)] bg-white/70"
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
              <button
                className={`mt-8 w-full rounded-full px-5 py-3 text-sm font-semibold ${
                  plan.highlight
                    ? "bg-[var(--primary)] text-white"
                    : "border border-[var(--stroke)] text-[var(--navy)]"
                }`}
              >
                Select Plan
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
