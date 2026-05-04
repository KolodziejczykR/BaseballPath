"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import Link from "next/link";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";
import { FadeOnScroll } from "@/components/ui/fade-on-scroll";
import { CheckCircle2, Menu, X, ArrowRight } from "lucide-react";
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";

export default function Home() {
  const supabase = useMemo(() => {
    try {
      return getSupabaseBrowserClient();
    } catch {
      return null;
    }
  }, []);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Swap the body's warm gradient + noise overlay for the cool canvas while
  // this page is mounted. Other routes keep their warm look.
  useEffect(() => {
    document.body.classList.add("landing-body");
    return () => document.body.classList.remove("landing-body");
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      gsap.registerPlugin(ScrollTrigger);
    }
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!supabase) return;
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setIsAuthenticated(Boolean(data.session));
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return;
      setIsAuthenticated(Boolean(session));
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [supabase]);

  const heroRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!heroRef.current) return;
    const ctx = gsap.context(() => {
      gsap.from(".hero-stagger", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        stagger: 0.08,
        ease: "power3.out",
      });
      gsap.from(".hero-card", {
        y: 40,
        opacity: 0,
        duration: 0.9,
        delay: 0.5,
        ease: "power3.out",
      });
    }, heroRef);
    return () => ctx.revert();
  }, []);

  return (
    <div className="min-h-screen relative bg-[var(--cool-canvas)] text-[var(--cool-ink)]">
      {/* A. NAVBAR */}
      <div className="fixed top-6 left-0 right-0 z-50 flex justify-center px-4 transition-all duration-300">
        <nav
          className={`flex items-center justify-between transition-all duration-500 rounded-full px-6 py-3 w-full max-w-4xl max-md:max-w-[calc(100vw-32px)] ${scrolled
            ? "bg-white/80 backdrop-blur-xl border border-[var(--cool-stroke)] text-[var(--cool-ink)] shadow-cool"
            : "bg-transparent text-[var(--cool-ink)]"
            }`}
        >
          <Link
            href="/"
            className="text-sm uppercase tracking-[0.28em] font-semibold text-[var(--cool-ink)] flex items-center gap-2"
          >
            BaseballPath
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium">
            <Link
              href="#how-it-works"
              className="transition-colors text-[var(--cool-ink-muted)] hover:text-[var(--cool-ink)]"
            >
              How It Works
            </Link>
            <Link
              href="#demo"
              className="transition-colors text-[var(--cool-ink-muted)] hover:text-[var(--cool-ink)]"
            >
              See It In Action
            </Link>
            <Link
              href="#pricing"
              className="transition-colors text-[var(--cool-ink-muted)] hover:text-[var(--cool-ink)]"
            >
              Pricing
            </Link>
          </div>
          <div className="hidden md:block">
            <Link
              href="/predict"
              className="inline-flex items-center bg-[var(--burnt-sienna)] text-white rounded-full px-5 py-2.5 text-sm font-semibold transition-transform duration-300 hover:scale-[1.03] shadow-cool"
            >
              {isAuthenticated ? "New Evaluation" : "Get my projection"}
            </Link>
          </div>
          <button
            className="md:hidden text-[var(--cool-ink)]"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </nav>
      </div>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-[var(--cool-canvas)]/97 backdrop-blur-lg flex flex-col items-center justify-center gap-8 text-xl font-medium text-[var(--cool-ink)] md:hidden">
          <Link href="#how-it-works" onClick={() => setMobileMenuOpen(false)}>
            How It Works
          </Link>
          <Link href="#demo" onClick={() => setMobileMenuOpen(false)}>
            See It In Action
          </Link>
          <Link href="#pricing" onClick={() => setMobileMenuOpen(false)}>
            Pricing
          </Link>
          <Link
            href="/predict"
            onClick={() => setMobileMenuOpen(false)}
            className="bg-[var(--burnt-sienna)] text-white rounded-full px-8 py-3"
          >
            {isAuthenticated ? "New Evaluation" : "Get my projection"}
          </Link>
        </div>
      )}

      <main>
        {/* B. HERO */}
        <section
          ref={heroRef}
          className="min-h-[100dvh] flex flex-col items-center justify-center relative pt-32 pb-20 px-6"
        >
          <div className="max-w-3xl w-full mx-auto text-center">
            <p className="hero-stagger text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">
              Honest Recruiting Evaluation
            </p>
            <h1 className="hero-stagger display-font text-6xl md:text-8xl lg:text-[6rem] font-semibold text-[var(--cool-ink)] mt-5 leading-[1.02] tracking-tight">
              See where you actually fit.
            </h1>
            <p className="hero-stagger text-lg md:text-xl text-[var(--cool-ink-muted)] max-w-xl mx-auto mt-7 leading-relaxed">
              We compare your numbers against 50,000+ college players when they were in your shoes — and show you the schools where your profile actually lands.
            </p>
            <div className="hero-stagger mt-10 flex flex-wrap gap-3 justify-center items-center">
              <Link
                href="/predict"
                className="inline-flex items-center gap-2 bg-[var(--burnt-sienna)] text-white rounded-full px-7 py-3.5 text-base font-semibold shadow-cool hover:-translate-y-0.5 hover:shadow-cool-strong transition-all duration-300"
              >
                See my matches <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="#how-it-works"
                className="inline-flex items-center justify-center rounded-full border border-[var(--cool-stroke-strong)] bg-white px-6 py-3.5 text-[var(--cool-ink)] font-semibold hover:bg-[var(--cool-surface-2)] transition-colors duration-300"
              >
                How it works
              </Link>
            </div>
          </div>

          <div className="hero-card mt-20 w-full max-w-xl mx-auto">
            <p className="text-[10px] uppercase tracking-[0.22em] text-[var(--cool-ink-muted)] text-center mb-3">
              Sample of a real evaluation
            </p>
            <EvalCardMock
              rank={1}
              school="Boston College"
              logoSlug="boston-college"
              tier="Power 4"
              meta="ACC · Chestnut Hill, MA"
              baseballFit={{ label: "Fit", kind: "fit" }}
              academicFit={{ label: "Reach", kind: "reach" }}
              rosterStatus="Open"
            />
          </div>
        </section>

        {/* C. HOW IT WORKS */}
        <section id="how-it-works" className="py-28 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold text-center">
              How It Works
            </p>
            <h2 className="display-font text-4xl md:text-5xl text-center text-[var(--cool-ink)] font-semibold mt-4 mb-16 leading-tight tracking-tight">
              Enter your stats for your personalized school list.
            </h2>
          </FadeOnScroll>
          <div className="grid md:grid-cols-3 gap-5">
            {[
              {
                num: "01",
                title: "Add your metrics",
                desc: "Enter your measurables and stats — height, fastball velo, exit velo, GPA, test scores. Takes under two minutes.",
              },
              {
                num: "02",
                title: "See where you land",
                desc: "We compare you against 50,000+ college players and project the division where you can succeed.",
              },
              {
                num: "03",
                title: "Get your school list",
                desc: "A ranked list of programs that match your profile — with academic, baseball, and live-roster context on each.",
              },
            ].map((step, i) => (
              <FadeOnScroll key={step.num} delayMs={i * 120}>
                <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface)] p-7 h-full shadow-cool transition-transform duration-300 hover:-translate-y-1">
                  <p className="font-mono text-xs text-[var(--cool-ink-muted)] tracking-widest">
                    {step.num}
                  </p>
                  <h3 className="text-xl font-semibold text-[var(--cool-ink)] mt-3">
                    {step.title}
                  </h3>
                  <p className="text-sm text-[var(--cool-ink-muted)] leading-relaxed mt-3">
                    {step.desc}
                  </p>
                </div>
              </FadeOnScroll>
            ))}
          </div>
        </section>

        {/* D. RAW STATS → RANKED SCHOOLS DEMO */}
        <section id="demo" className="py-28 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold text-center">
              See It In Action
            </p>
            <h2 className="display-font text-4xl md:text-5xl text-center text-[var(--cool-ink)] font-semibold mt-4 leading-tight tracking-tight">
              From metrics to matches.
            </h2>
            <p className="text-base md:text-lg text-[var(--cool-ink-muted)] text-center mt-5 max-w-xl mx-auto">
              Your stats become a real target list in under 90 seconds. See the same view your evaluation produces.
            </p>
          </FadeOnScroll>

          <div className="mt-14 grid md:grid-cols-2 gap-6 items-stretch">
            <FadeOnScroll>
              <div className="h-full">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[var(--cool-ink-muted)] mb-3 ml-1">
                  Your inputs
                </p>
                <RawStatsMock />
              </div>
            </FadeOnScroll>
            <FadeOnScroll delayMs={150}>
              <div className="h-full">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[var(--cool-ink-muted)] mb-3 ml-1">
                  Your top match
                </p>
                <ExpandedEvalCardMock />
              </div>
            </FadeOnScroll>
          </div>
        </section>

        {/* E. SCHOOL CARD CYCLER — works for every level of recruit */}
        <section className="py-28 px-6 max-w-5xl mx-auto">
          <FadeOnScroll>
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold text-center">
              Every Level, Every Recruit
            </p>
            <h2 className="display-font text-4xl md:text-5xl text-center text-[var(--cool-ink)] font-semibold mt-4 mb-3 leading-tight tracking-tight">
              Built for D1 to D3.
            </h2>
            <p className="text-base md:text-lg text-[var(--cool-ink-muted)] text-center mb-4 max-w-xl mx-auto">
              Most tools optimize for one tier. Ours runs the same evaluation across every division - because the difference between the SEC and D3 is data, not opinion.
            </p>
            <p className="italic text-base md:text-lg text-[var(--cool-ink-muted)] text-center mb-10 max-w-xl mx-auto">
              See how the same model evaluates three different player profiles:
            </p>
          </FadeOnScroll>
          <FadeOnScroll>
            <SchoolCardCycler />
          </FadeOnScroll>
        </section>

        {/* F. TRUST / STATS */}
        <section className="py-24 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold text-center">
              Built On Real Data
            </p>
            <h2 className="display-font text-4xl md:text-5xl text-center text-[var(--cool-ink)] font-semibold mt-4 mb-14 leading-tight tracking-tight">
              Evidence over opinion.
            </h2>
          </FadeOnScroll>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            {[
              { val: "50,000+", lbl: "College player profiles in the model" },
              { val: "D1 → D3", lbl: "Every division evaluated with the same model, no school left as an afterthought." },
              { val: "~90 sec", lbl: "From your form submission to projection" },
              { val: "Live rosters", lbl: "Current college lineups and projected departures factored into every match." },
            ].map((m, i) => (
              <FadeOnScroll key={m.val} delayMs={i * 80}>
                <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface)] p-6 h-full shadow-cool">
                  <p className="display-font text-3xl md:text-4xl font-semibold text-[var(--cool-ink)] tracking-tight">
                    {m.val}
                  </p>
                  <p className="text-xs text-[var(--cool-ink-muted)] leading-relaxed mt-3">
                    {m.lbl}
                  </p>
                </div>
              </FadeOnScroll>
            ))}
          </div>
        </section>

        {/* F2. WHAT THIS ISN'T */}
        <section className="py-28 px-6 max-w-3xl mx-auto">
          <FadeOnScroll>
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold text-center">
              What We Don&apos;t Do
            </p>
            <h2 className="display-font text-4xl md:text-5xl text-center text-[var(--cool-ink)] font-semibold mt-4 mb-10 leading-tight tracking-tight">
              We&apos;re not a recruiting service.
            </h2>
            <p className="text-base md:text-lg text-[var(--cool-ink-muted)] leading-relaxed mb-6">
              We don&apos;t email coaches for you. We don&apos;t promise placement. We don&apos;t keep charging you to &ldquo;stay engaged.&rdquo;
            </p>
            <p className="text-base md:text-lg text-[var(--cool-ink-muted)] leading-relaxed mb-6">
              Most recruiting services are paid to keep your dream alive. We&apos;re paid once to tell you the truth — based on current college rosters, the players already on those teams, and where your numbers actually land against them.
            </p>
            <p className="italic text-sm md:text-base text-[var(--cool-ink-muted)] leading-relaxed">
              One honest snapshot. A real school list. No spin.
            </p>
          </FadeOnScroll>
        </section>

        {/* G. PRICING */}
        <section id="pricing" className="py-28 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold text-center">
              Pricing
            </p>
            <h2 className="display-font text-4xl md:text-5xl text-center text-[var(--cool-ink)] font-semibold mt-4 mb-4 leading-tight tracking-tight">
              Free during beta. Honest pricing after.
            </h2>
            <p className="text-center text-[var(--cool-ink-muted)] mb-6 max-w-xl mx-auto text-base md:text-lg">
              Pay nothing while we&apos;re in beta. 
              After launch, BaseballPath evaluations stay a one-time purchase. 
            </p>
            <p className="italic text-center text-[var(--cool-ink-muted)] mb-14 max-w-xl mx-auto text-base md:text-lg">
              No subscription, no incentive to keep you guessing.
            </p>
          </FadeOnScroll>
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto items-stretch">
            <FadeOnScroll>
              <div className="rounded-2xl p-8 shadow-cool-strong ring-1 ring-[var(--burnt-sienna)] relative bg-[var(--cool-surface)] flex flex-col h-full">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[var(--burnt-sienna)] text-white font-bold uppercase tracking-widest text-[10px] px-3 py-1 rounded-full whitespace-nowrap">
                  First Evaluation
                </div>
                <h3 className="text-xl font-bold text-[var(--cool-ink)] mb-2">
                  Your First Report ($69 Value)
                </h3>
                {/* FREE BETA: original price was $69 — restore when paid checkout is re-enabled */}
                {/* <p className="display-font text-5xl font-semibold text-[var(--cool-ink)] mb-6">$69</p> */}
                <p className="display-font text-5xl font-semibold text-[var(--cool-ink)] mb-6">
                  Free
                </p>
                <div className="flex-grow">
                  <ul className="space-y-3.5 mb-8 text-sm text-[var(--cool-ink)] font-medium">
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Data-backed division projection
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Up to 25 best-fit school matches
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Personalized fit summaries
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Academic + athletic comparisons
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Save & compare your schools
                    </li>
                  </ul>
                </div>
                <Link
                  href="/predict"
                  className="block w-full text-center bg-[var(--burnt-sienna)] text-white rounded-full px-6 py-3 font-semibold shadow-cool hover:scale-[1.02] transition-transform mt-auto"
                >
                  Get Your Evaluation
                </Link>
              </div>
            </FadeOnScroll>

            <FadeOnScroll delayMs={150}>
              <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface)] p-8 shadow-cool flex flex-col h-full">
                <h3 className="text-xl font-bold text-[var(--cool-ink)] mb-2">
                  Additional Evals ($29 Value)
                </h3>
                {/* FREE BETA: original price was $29 each — restore when paid checkout is re-enabled */}
                {/* <p className="display-font text-5xl font-semibold text-[var(--cool-ink)] mb-6">$29<span className="text-base text-[var(--cool-ink-muted)] font-sans font-normal"> each</span></p> */}
                <p className="display-font text-5xl font-semibold text-[var(--cool-ink)] mb-6">
                  Free
                </p>
                <div className="flex-grow">
                  <ul className="space-y-3.5 mb-8 text-sm text-[var(--cool-ink-muted)]">
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Same full evaluation report
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Update your metrics anytime
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Re-run with different positions
                    </li>
                    <li className="flex gap-2.5">
                      <CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0 mt-0.5" />
                      Adjust preferences & compare
                    </li>
                  </ul>
                </div>
                <Link
                  href="/predict"
                  className="block w-full text-center rounded-full border border-[var(--cool-stroke-strong)] px-6 py-3 font-semibold text-[var(--cool-ink)] hover:bg-[var(--cool-surface-2)] transition-colors mt-auto"
                >
                  Run Another Evaluation
                </Link>
              </div>
            </FadeOnScroll>
          </div>
        </section>

        {/* H. FINAL CTA */}
        <section className="py-32 px-6 text-center relative overflow-hidden">
          <div className="max-w-2xl mx-auto relative z-10">
            <FadeOnScroll>
              <h2 className="display-font text-5xl md:text-6xl text-[var(--cool-ink)] font-semibold mb-5 leading-tight tracking-tight">
                See where you actually fit.
              </h2>
              <p className="italic text-base md:text-lg text-[var(--cool-ink-muted)] mb-5 max-w-xl mx-auto">
                For the players ready to hear the truth. For the parents who need real answers.
              </p>
              <p className="text-lg md:text-xl text-[var(--cool-ink-muted)] mb-10">
                Two minutes. Real data. No credit card.
              </p>
              <Link
                href="/predict"
                className="inline-flex items-center gap-2 bg-[var(--burnt-sienna)] text-white rounded-full px-10 py-4 text-lg font-semibold shadow-cool-strong hover:-translate-y-0.5 transition-transform duration-300"
              >
                Get my evaluation <ArrowRight className="w-5 h-5" />
              </Link>
              <p className="text-base md:text-lg text-[var(--cool-ink)] font-semibold mt-7">
                Free for the first 50 players in beta
                <span className="text-[var(--cool-ink-muted)] font-normal"> (then $69)</span>
              </p>
            </FadeOnScroll>
          </div>
        </section>
      </main>

      {/* I. FOOTER */}
      <footer className="bg-[var(--cool-ink)] text-white/80 rounded-t-[3rem] px-6 pt-20 pb-10 mx-auto w-full relative z-20 overflow-hidden">
        <div className="max-w-6xl mx-auto grid md:grid-cols-4 gap-12 mb-16">
          <div className="col-span-1 md:col-span-1">
            <h3 className="text-sm uppercase tracking-[0.3em] font-semibold text-white mb-4">
              BaseballPath
            </h3>
            <p className="text-white/55 text-sm leading-relaxed">
              Honest recruiting evaluations, built on real data.
            </p>
          </div>
          <div>
            <h4 className="text-white/60 text-xs uppercase tracking-widest font-bold mb-4">
              Product
            </h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li>
                <Link href="#how-it-works" className="hover:text-white transition-colors">
                  How It Works
                </Link>
              </li>
              <li>
                <Link href="#demo" className="hover:text-white transition-colors">
                  See It In Action
                </Link>
              </li>
              <li>
                <Link href="#pricing" className="hover:text-white transition-colors">
                  Pricing
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-white/60 text-xs uppercase tracking-widest font-bold mb-4">
              Company
            </h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li>
                <Link href="/about" className="hover:text-white transition-colors">
                  About
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Privacy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-white/60 text-xs uppercase tracking-widest font-bold mb-4">
              Connect
            </h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li>
                <a href="#" className="hover:text-white transition-colors">
                  Twitter / X
                </a>
              </li>
              <li>
                <a href="#" className="hover:text-white transition-colors">
                  Instagram
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="max-w-6xl mx-auto border-t border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-white/40">
          <p>&copy; 2026 BaseballPath. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Eval-card mocks. Visual fidelity matches frontend/src/app/evaluations/[runId]/page.tsx
// so the demo shows users exactly what their real eval produces.
// ──────────────────────────────────────────────────────────────────────────

const MEDAL_COLORS = ["#D4A843", "#C0C0C0", "#CD7F32"] as const;

type FitKind = "fit" | "reach" | "safety";
type RosterStatus = "Open" | "Crowded" | "Competitive";

function RankMedal({ rank }: { rank: number }) {
  if (rank > 3) {
    return (
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--cool-surface-2)] text-xs font-bold text-[var(--cool-ink)]">
        {rank}
      </div>
    );
  }
  return (
    <div
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
      style={{ background: MEDAL_COLORS[rank - 1] }}
    >
      {rank}
    </div>
  );
}

const FIT_STYLES: Record<FitKind, { bg: string; text: string; border: string }> = {
  fit: { bg: "rgba(107,143,94,0.14)", text: "#5A7A4F", border: "rgba(107,143,94,0.55)" },
  reach: { bg: "rgba(184,115,51,0.14)", text: "#9C5F2A", border: "rgba(184,115,51,0.55)" },
  safety: { bg: "rgba(212,168,67,0.18)", text: "#8A6B1F", border: "rgba(212,168,67,0.6)" },
};

function FitBadge({ label, kind }: { label: string; kind: FitKind }) {
  const c = FIT_STYLES[kind];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
    >
      {label}
    </span>
  );
}

// Stoplight semantics — Open is good, Competitive is contested, Crowded is
// the most important signal ("no roster room"). Mirrors the eval page's
// RosterBadge in components/evaluation/school-display.tsx.
const ROSTER_STYLES: Record<RosterStatus, { bg: string; text: string }> = {
  Open: { bg: "#dcfce7", text: "#166534" },
  Competitive: { bg: "#fef3c7", text: "#92400e" },
  Crowded: { bg: "#fee2e2", text: "#b91c1c" },
};

function RosterBadge({ status }: { status: RosterStatus }) {
  const c = ROSTER_STYLES[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ background: c.bg, color: c.text }}
    >
      Roster: {status}
    </span>
  );
}

function TierBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-[var(--cool-surface-2)] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--cool-ink)] border border-[var(--cool-stroke)]">
      {label}
    </span>
  );
}

function SchoolGlyph({ name, size = 40 }: { name: string; size?: number }) {
  const initials = name
    .split(" ")
    .filter(w => w[0] && /[A-Z]/.test(w[0]))
    .slice(0, 2)
    .map(w => w[0])
    .join("");
  return (
    <div
      className="shrink-0 flex items-center justify-center rounded-lg border border-[var(--cool-stroke)] bg-[var(--cool-surface-2)] font-bold text-[var(--cool-ink-muted)]"
      style={{ width: size, height: size, fontSize: size * 0.32 }}
    >
      {initials || "·"}
    </div>
  );
}

// Real NCAA logos via the same public API the eval results page uses
// (frontend/src/app/evaluations/[runId]/page.tsx:138). Falls back to the
// initials glyph if the logo fails to load.
function SchoolLogo({ slug, name, size = 44 }: { slug?: string; name: string; size?: number }) {
  const [errored, setErrored] = useState(false);
  if (!slug || errored) {
    return <SchoolGlyph name={name} size={size} />;
  }
  const url = `https://ncaa-api.henrygd.me/logo/${encodeURIComponent(slug)}.svg`;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={name}
      loading="lazy"
      onError={() => setErrored(true)}
      className="shrink-0 rounded-lg border border-[var(--cool-stroke)] bg-white p-1.5 object-contain"
      style={{ width: size, height: size }}
    />
  );
}

type EvalCardProps = {
  rank: number;
  school: string;
  logoSlug?: string;
  tier: string;
  meta: string;
  baseballFit: { label: string; kind: FitKind };
  academicFit: { label: string; kind: FitKind };
  rosterStatus: RosterStatus;
};

function EvalCardMock(props: EvalCardProps) {
  return (
    <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface)] p-6 md:p-7 shadow-cool-strong">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3.5 min-w-0">
          <RankMedal rank={props.rank} />
          <div className="min-w-0">
            <p className="text-lg md:text-xl font-semibold text-[var(--cool-ink)] truncate">
              {props.school}
            </p>
            <p className="mt-1 text-sm text-[var(--cool-ink-muted)]">{props.meta}</p>
          </div>
        </div>
        <SchoolLogo slug={props.logoSlug} name={props.school} size={52} />
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <TierBadge label={props.tier} />
        <FitBadge label={`Baseball: ${props.baseballFit.label}`} kind={props.baseballFit.kind} />
        <FitBadge label={`Academic: ${props.academicFit.label}`} kind={props.academicFit.kind} />
        <RosterBadge status={props.rosterStatus} />
      </div>
    </div>
  );
}

function ExpandedEvalCardMock() {
  return (
    <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface)] p-6 md:p-7 shadow-cool h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3.5 min-w-0">
          <RankMedal rank={1} />
          <div className="min-w-0">
            <h3 className="text-lg md:text-xl font-bold text-[var(--cool-ink)]">Connecticut Huskies</h3>
            <p className="mt-1 text-sm text-[var(--cool-ink-muted)]">
              Big East · Storrs, CT
            </p>
          </div>
        </div>
        <SchoolLogo slug="uconn" name="Connecticut Huskies" size={56} />
      </div>

      {/* Badge cluster */}
      <div className="mt-5 flex flex-wrap gap-2">
        <TierBadge label="Division 1" />
        <FitBadge label="Baseball: Fit" kind="fit" />
        <FitBadge label="Academic: Fit" kind="fit" />
        <RosterBadge status="Open" />
      </div>

      {/* Data boxes */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-[var(--cool-stroke)] bg-[var(--cool-surface-2)] p-3.5">
          <p className="text-[10px] uppercase tracking-wider text-[var(--cool-ink-muted)]">
            Academic selectivity
          </p>
          <p className="mt-1 text-sm font-semibold text-[var(--cool-ink)]">6.0 / 10</p>
        </div>
        <div className="rounded-xl border border-[var(--cool-stroke)] bg-[var(--cool-surface-2)] p-3.5">
          <p className="text-[10px] uppercase tracking-wider text-[var(--cool-ink-muted)]">
            Annual cost
          </p>
          <p className="mt-1 text-sm font-semibold text-[var(--cool-ink)]">$43,034</p>
        </div>
      </div>

      {/* Why this school */}
      <div className="mt-5 rounded-xl border border-[var(--cool-stroke)] bg-[var(--cool-surface-2)] p-4">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--cool-ink-muted)] font-semibold">
          Why this school
        </p>
        <p className="mt-2 text-sm leading-relaxed text-[var(--cool-ink)]">
          Your 6&prime;1&Prime;, 185 lb frame and 92 mph exit velo land in the Big East&apos;s middle 60% for shortstops, and the roster has two SS departures projected next season. Your 3.61 GPA fits the program&apos;s academic profile.
        </p>
      </div>
    </div>
  );
}

function RawStatsMock() {
  const stats = [
    { label: "Height", value: "6′1″" },
    { label: "Weight", value: "185 lb" },
    { label: "60-yard dash", value: "6.78s" },
    { label: "Exit velocity", value: "92 mph" },
    { label: "Infield velocity", value: "84 mph" },
    { label: "GPA (unweighted)", value: "3.61" },
  ];
  return (
    <div className="rounded-2xl border border-[var(--cool-stroke)] bg-[var(--cool-surface)] p-6 md:p-7 shadow-cool h-full">
      <div className="flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--cool-ink-muted)] font-semibold">
          Your profile
        </p>
        <span className="inline-flex items-center rounded-full bg-[var(--cool-surface-2)] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--cool-ink)] border border-[var(--cool-stroke)]">
          Shortstop · Class of 2027
        </span>
      </div>
      <div className="mt-5 divide-y divide-[var(--cool-stroke)]">
        {stats.map(s => (
          <div key={s.label} className="flex items-center justify-between py-3.5">
            <p className="text-sm text-[var(--cool-ink-muted)]">{s.label}</p>
            <p className="text-sm font-mono font-semibold text-[var(--cool-ink)]">{s.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-2 pt-4 border-t border-[var(--cool-stroke)]">
        <p className="text-[11px] text-[var(--cool-ink-muted)] leading-relaxed">
          Plus academic test scores, target preferences, and more.
        </p>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Interactive cycler — three player archetypes, one card visible at a time.
// ──────────────────────────────────────────────────────────────────────────

const ARCHETYPES: { tab: string; card: EvalCardProps }[] = [
  {
    tab: "Power 4 prospect",
    card: {
      rank: 4,
      school: "Georgia",
      logoSlug: "georgia",
      tier: "Power 4",
      meta: "SEC · Athens, GA",
      baseballFit: { label: "Reach", kind: "reach" },
      academicFit: { label: "Fit", kind: "fit" },
      rosterStatus: "Crowded",
    },
  },
  {
    tab: "D2 Champion",
    card: {
      rank: 1,
      school: "University of Tampa",
      logoSlug: "tampa",
      tier: "Division 2",
      meta: "SSC · Tampa, FL",
      baseballFit: { label: "Fit", kind: "fit" },
      academicFit: { label: "Fit", kind: "fit" },
      rosterStatus: "Competitive",
    },
  },
  {
    tab: "High Academic D3",
    card: {
      rank: 3,
      school: "Middlebury College",
      logoSlug: "middlebury",
      tier: "Division 3",
      meta: "NESCAC · Middlebury, VT",
      baseballFit: { label: "Safety", kind: "safety" },
      academicFit: { label: "Reach", kind: "reach" },
      rosterStatus: "Open",
    },
  },
];

function SchoolCardCycler() {
  const [active, setActive] = useState(0);
  return (
    <div>
      <div className="flex flex-wrap justify-center gap-2 mb-8">
        {ARCHETYPES.map((a, i) => {
          const isActive = i === active;
          return (
            <button
              key={a.tab}
              onClick={() => setActive(i)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-all duration-200 ${isActive
                  ? "bg-[var(--cool-ink)] text-white shadow-cool"
                  : "bg-[var(--cool-surface)] text-[var(--cool-ink-muted)] border border-[var(--cool-stroke)] hover:text-[var(--cool-ink)]"
                }`}
            >
              {a.tab}
            </button>
          );
        })}
      </div>
      <div className="max-w-xl mx-auto" key={active}>
        <EvalCardMock {...ARCHETYPES[active].card} />
      </div>
    </div>
  );
}
