import { FadeOnScroll } from "@/components/ui/fade-on-scroll";
import Link from "next/link";

const featureCards = [
  {
    title: "Division Projection",
    desc: "Forecast D1 versus non-D1 and Power 4 upside from the profile coaches care about most.",
  },
  {
    title: "School Fit Ranking",
    desc: "Sort schools by academics, roster opportunity, region, and budget in one report.",
  },
  {
    title: "Playing-Time Signal",
    desc: "Convert roster context into a clear playing-time estimate so decisions are concrete.",
  },
  {
    title: "AI Reasoning Layer",
    desc: "Get concise context for why each school matches your specific profile and goals.",
  },
];

const processCards = [
  {
    label: "01",
    title: "Profile intake",
    desc: "Name, state, graduating class, and position establish your recruiting context.",
  },
  {
    label: "02",
    title: "Position metrics",
    desc: "We only ask for the stat set that matches your primary position.",
  },
  {
    label: "03",
    title: "Preference filter",
    desc: "Campus, academic, and cost preferences shape your final school ranking.",
  },
];

const signals = [
  { value: "1200+", label: "NCAA programs considered" },
  { value: "3-step", label: "Guided prediction workflow" },
  { value: "< 2 min", label: "Typical profile completion time" },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-black/10 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[var(--navy)] text-sm font-bold tracking-wide text-white">
              BP
            </div>
            <div className="leading-tight">
              <p className="text-xs uppercase tracking-[0.34em] text-[var(--muted)]">BaseballPath</p>
              <p className="text-base font-semibold">Recruiting Intelligence</p>
            </div>
          </Link>
          <nav className="hidden items-center gap-6 text-sm font-medium text-[var(--muted)] md:flex">
            <Link href="/predict" className="hover:text-[var(--foreground)]">
              Predict
            </Link>
            <Link href="/plans" className="hover:text-[var(--foreground)]">
              Plans
            </Link>
            <Link href="/waitlist" className="hover:text-[var(--foreground)]">
              Waitlist
            </Link>
            <Link href="/login" className="hover:text-[var(--foreground)]">
              Login
            </Link>
            <Link
              href="/signup"
              className="rounded-full bg-[var(--accent)] px-5 py-2.5 font-semibold text-white shadow-strong transition-transform duration-300 hover:-translate-y-0.5 hover:opacity-95"
            >
              Signup
            </Link>
          </nav>
        </div>
      </header>

      <main className="relative overflow-hidden px-6 pb-24 pt-12">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[540px] bg-[radial-gradient(900px_420px_at_20%_0%,rgba(241,115,36,0.22),transparent_60%),radial-gradient(800px_360px_at_95%_5%,rgba(15,74,129,0.2),transparent_55%)]" />

        <section className="relative mx-auto grid max-w-6xl gap-12 md:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="text-xs uppercase tracking-[0.42em] text-[var(--muted)]">AI Baseball Recruiting</p>
            <h1 className="display-font mt-5 max-w-2xl text-5xl leading-[1.02] md:text-7xl">
              Build a recruiting plan that feels clear before your first call.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-[var(--muted)]">
              BaseballPath transforms profile metrics into division projection, school fit, and playing-time
              opportunity so players and families can move with confidence.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link
                href="/predict"
                className="rounded-full bg-[var(--primary)] px-7 py-3.5 text-sm font-semibold text-white shadow-strong transition-transform duration-300 hover:-translate-y-0.5"
              >
                Launch Prediction Pipeline
              </Link>
              <Link
                href="/plans"
                className="rounded-full border border-[var(--stroke)] bg-white/70 px-7 py-3.5 text-sm font-semibold text-[var(--navy)]"
              >
                Compare Plans
              </Link>
            </div>
            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {signals.map((signal, index) => (
                <FadeOnScroll key={signal.label} delayMs={index * 80}>
                  <div className="glass rounded-2xl p-4 shadow-soft">
                    <p className="text-2xl font-bold text-[var(--navy)]">{signal.value}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">{signal.label}</p>
                  </div>
                </FadeOnScroll>
              ))}
            </div>
          </div>

          <FadeOnScroll className="h-fit">
            <div className="glass relative overflow-hidden rounded-[30px] p-7 shadow-strong">
              <div className="absolute -right-16 -top-14 h-44 w-44 rounded-full bg-[var(--accent)]/25 blur-2xl" />
              <div className="absolute -bottom-20 -left-8 h-52 w-52 rounded-full bg-[var(--primary)]/20 blur-2xl" />

              <div className="relative">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-[0.28em] text-[var(--muted)]">Sample Recommendation</p>
                  <span className="rounded-full bg-[var(--navy)]/10 px-3 py-1 text-xs font-semibold text-[var(--navy)]">
                    Live-style Preview
                  </span>
                </div>
                <div className="mt-6 space-y-4">
                  {["UC Irvine", "Cal State Fullerton", "Arizona State"].map((school, index) => (
                    <FadeOnScroll key={school} delayMs={index * 80}>
                      <article className="rounded-2xl border border-[var(--stroke)] bg-white/78 p-4">
                        <div className="flex items-center justify-between">
                          <p className="font-semibold">{school}</p>
                          <span className="rounded-full bg-[var(--sand)] px-2.5 py-1 text-xs font-semibold text-[var(--navy)]">
                            Non-P4 D1
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-[var(--muted)]">
                          Strong roster opportunity, balanced academics, and a strong geographic fit.
                        </p>
                      </article>
                    </FadeOnScroll>
                  ))}
                </div>
              </div>
            </div>
          </FadeOnScroll>
        </section>

        <section className="relative mx-auto mt-20 max-w-6xl">
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {featureCards.map((card, index) => (
              <FadeOnScroll key={card.title} delayMs={index * 70}>
                <div className="glass h-full rounded-3xl p-6 shadow-soft">
                  <p className="text-lg font-semibold">{card.title}</p>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{card.desc}</p>
                </div>
              </FadeOnScroll>
            ))}
          </div>
        </section>

        <section className="relative mx-auto mt-20 grid max-w-6xl gap-8 md:grid-cols-[0.92fr_1.08fr]">
          <FadeOnScroll>
            <div className="relative overflow-hidden rounded-[34px] bg-[var(--navy)] p-8 text-white shadow-strong md:p-10">
              <div className="absolute right-0 top-0 h-36 w-36 rounded-bl-[80px] bg-white/8" />
              <p className="text-xs uppercase tracking-[0.36em] text-white/60">How It Works</p>
              <h2 className="display-font mt-4 text-4xl leading-tight md:text-5xl">
                A recruiting workflow that follows coach logic.
              </h2>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/75">
                We guide athletes through the right sequence: identity first, position data second, then preference
                filters for final school fit.
              </p>
              <Link
                href="/predict"
                className="mt-7 inline-flex items-center justify-center rounded-full bg-white px-5 py-2.5 text-sm font-semibold !text-[var(--navy)]"
                style={{ color: "var(--navy)" }}
              >
                Open Prediction Pipeline
              </Link>
            </div>
          </FadeOnScroll>

          <div className="grid gap-5">
            {processCards.map((card, index) => (
              <FadeOnScroll key={card.label} delayMs={index * 90}>
                <article className="glass rounded-2xl p-6 shadow-soft">
                  <p className="text-xs uppercase tracking-[0.32em] text-[var(--muted)]">Step {card.label}</p>
                  <p className="mt-2 text-xl font-semibold">{card.title}</p>
                  <p className="mt-2 text-sm text-[var(--muted)]">{card.desc}</p>
                </article>
              </FadeOnScroll>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
