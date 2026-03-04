"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import Link from "next/link";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";
import { FadeOnScroll } from "@/components/ui/fade-on-scroll";
import {
  CheckCircle2,
  BarChart3,
  Target,
  Share2,
  MousePointer2,
  Menu,
  X
} from "lucide-react";
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
        ease: "power3.out"
      });
      gsap.from(".hero-card", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: 0.4,
        ease: "power3.out"
      });
    }, heroRef);
    return () => ctx.revert();
  }, []);

  return (
    <div className="min-h-screen relative">
      {/* A. NAVBAR */}
      <div className="fixed top-6 left-0 right-0 z-50 flex justify-center px-4 transition-all duration-300">
        <nav
          className={`flex items-center justify-between transition-all duration-500 rounded-full px-6 py-3 w-full max-w-4xl max-md:max-w-[calc(100vw-32px)] ${scrolled
            ? "bg-[var(--warm-cream)]/60 backdrop-blur-xl border border-[var(--clay-mist)] text-[var(--espresso)] shadow-soft"
            : "bg-transparent text-[var(--foreground)]"
            }`}
        >
          <Link href="/" className="text-sm uppercase tracking-[0.3em] font-semibold text-[var(--espresso)] flex items-center gap-2">
            BaseballPath
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium">
            <Link href="#how-it-works" className="hover:-translate-y-[1px] transition-transform text-[var(--muted)] hover:text-[var(--espresso)]">How It Works</Link>
            <Link href="#features" className="hover:-translate-y-[1px] transition-transform text-[var(--muted)] hover:text-[var(--espresso)]">Features</Link>
            <Link href="#pricing" className="hover:-translate-y-[1px] transition-transform text-[var(--muted)] hover:text-[var(--espresso)]">Pricing</Link>
          </div>
          <div className="hidden md:block">
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="overflow-hidden relative group inline-block bg-[var(--burnt-sienna)] text-white rounded-full px-6 py-2.5 text-sm font-semibold transition-transform hover:scale-[1.03] duration-300"
              >
                <span className="relative z-10">Dashboard &rarr;</span>
                <span className="absolute inset-0 bg-[var(--golden-sand)] translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out z-0"></span>
              </Link>
            ) : (
              <Link
                href="/predict"
                className="overflow-hidden relative group inline-block bg-[var(--burnt-sienna)] text-white rounded-full px-6 py-2.5 text-sm font-semibold transition-transform hover:scale-[1.03] duration-300"
              >
                <span className="relative z-10">Get Your Projection</span>
                <span className="absolute inset-0 bg-[var(--golden-sand)] translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out z-0"></span>
              </Link>
            )}
          </div>
          <button className="md:hidden text-[var(--espresso)]" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </nav>
      </div>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-[var(--warm-cream)]/95 backdrop-blur-lg flex flex-col items-center justify-center gap-8 text-xl font-medium text-[var(--espresso)] md:hidden">
          <Link href="#how-it-works" onClick={() => setMobileMenuOpen(false)}>How It Works</Link>
          <Link href="#features" onClick={() => setMobileMenuOpen(false)}>Features</Link>
          <Link href="#pricing" onClick={() => setMobileMenuOpen(false)}>Pricing</Link>
          {isAuthenticated ? (
            <Link href="/dashboard" onClick={() => setMobileMenuOpen(false)} className="bg-[var(--burnt-sienna)] text-white rounded-full px-8 py-3">Dashboard &rarr;</Link>
          ) : (
            <Link href="/predict" onClick={() => setMobileMenuOpen(false)} className="bg-[var(--burnt-sienna)] text-white rounded-full px-8 py-3">Get Your Projection</Link>
          )}
        </div>
      )}

      <main>
        {/* B. HERO SECTION */}
        <section ref={heroRef} className="min-h-[100dvh] flex items-center relative pt-32 pb-16 px-6">
          <div className="max-w-6xl mx-auto w-full grid md:grid-cols-[1.1fr_0.9fr] gap-12 items-center">
            <div>
              <p className="hero-stagger text-xs uppercase tracking-[0.2em] text-[var(--burnt-sienna)] font-semibold">Your AI Recruitment Assistant</p>
              <h1 className="hero-stagger display-font text-5xl md:text-7xl font-bold text-[var(--espresso)] mt-4 leading-[1.05]">
                Stop guessing.<br />
                <span className="text-[var(--burnt-sienna)] italic font-semibold">Know your best-fit schools.</span>
              </h1>
              <p className="hero-stagger text-lg text-[var(--muted)] max-w-md mt-6">
                BaseballPath uses real D1–D3 player data to project where you&apos;d compete — and what to improve to get there.
              </p>
              <ul className="hero-stagger mt-8 space-y-3">
                {[
                  <span key="1"><strong className="text-[var(--espresso)] font-bold">Division-level projections</strong> grounded in 49,000+ college profiles</span>,
                  <span key="2"><strong className="text-[var(--espresso)] font-bold">Personalized improvement goals</strong> based on your biggest leverage stats</span>
                ].map((pt, i) => (
                  <li key={i} className="flex gap-3 items-start text-[var(--espresso)]/80 text-sm md:text-base font-medium">
                    <CheckCircle2 className="w-5 h-5 text-[var(--sage-green)] shrink-0 mt-0.5" />
                    <span>{pt}</span>
                  </li>
                ))}
              </ul>
              <div className="hero-stagger mt-10 flex flex-wrap gap-4 items-center">
                <Link
                  href={isAuthenticated ? "/dashboard" : "/predict"}
                  className="overflow-hidden relative group inline-flex items-center justify-center bg-[var(--burnt-sienna)] text-white rounded-full px-8 py-3.5 text-base font-semibold shadow-soft hover:-translate-y-1 transition-all duration-300"
                >
                  <span className="relative z-10 transition-colors group-hover:text-white">Check my projection &rarr;</span>
                  <span className="absolute inset-0 bg-[var(--golden-sand)] translate-y-full group-hover:translate-y-0 transition-transform duration-400 ease-out z-0"></span>
                </Link>
                <Link
                  href="#how-it-works"
                  className="inline-flex items-center justify-center rounded-full border border-[var(--stroke)] px-6 py-3.5 text-[var(--walnut)] font-semibold hover:bg-[var(--stroke)]/20 transition-colors duration-300"
                >
                  See how it works
                </Link>
              </div>
            </div>

            <div className="hero-card relative w-full aspect-[4/5] max-w-sm mx-auto md:ml-auto glass rounded-[3rem] p-6 shadow-strong flex flex-col justify-between overflow-hidden border border-[var(--golden-sand)]/20 group">
              <div className="absolute top-[-20%] right-[-20%] w-[140%] h-[140%] bg-[radial-gradient(ellipse_at_top_right,rgba(212,168,67,0.15),transparent_60%)] pointer-events-none"></div>

              <div>
                <div className="flex justify-between items-start mb-6">
                  <img src="/BP-brown-logo-circle.png" alt="BaseballPath" className="w-12 h-12" />
                  <div className="bg-[var(--sage-green)]/10 text-[var(--sage-green)] px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider backdrop-blur-md">Projected</div>
                </div>

                <div className="space-y-4 relative z-10">
                  <div className="bg-[var(--parchment)]/60 rounded-2xl p-4 border border-[var(--stroke)] backdrop-blur-sm group-hover:-translate-y-1 transition-transform duration-300">
                    <p className="text-xs uppercase tracking-widest text-[var(--muted)] mb-1">Top Match</p>
                    <p className="font-bold text-xl text-[var(--espresso)]">Arizona State</p>
                    <div className="flex justify-between items-center mt-3">
                      <span className="bg-[var(--walnut)] text-[var(--warm-cream)] text-[10px] font-bold px-2 py-0.5 rounded uppercase">D1</span>
                      <span className="text-[var(--primary)] font-bold font-mono">82% Match</span>
                    </div>
                  </div>

                  <div className="bg-[var(--parchment)]/60 rounded-2xl p-4 border border-[var(--stroke)] backdrop-blur-sm transition-transform duration-300 delay-75 group-hover:-translate-y-1">
                    <p className="text-xs uppercase tracking-widest text-[var(--burnt-sienna)] mb-1">Top Leverage Stat</p>
                    <p className="font-bold text-lg text-[var(--espresso)] flex justify-between">Exit Velo <span>+4 mph</span></p>
                    <div className="w-full bg-[var(--sand)] rounded-full h-1.5 mt-2 overflow-hidden">
                      <div className="bg-[var(--burnt-sienna)] h-full w-[65%] rounded-full"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="text-center mt-6 relative z-10">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] font-semibold">Live Preview Artifact</p>
              </div>
            </div>
          </div>
        </section>

        {/* C. HOW IT WORKS */}
        <section id="how-it-works" className="py-24 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <h2 className="display-font text-3xl md:text-4xl text-center text-[var(--espresso)] font-bold mb-16">
              From first stat to first call &mdash; <span className="text-[var(--burnt-sienna)] italic">in three steps.</span>
            </h2>
          </FadeOnScroll>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                num: "01",
                icon: BarChart3,
                title: "Add your metrics",
                desc: "Enter your measurables, grades, and stats. Takes under two minutes."
              },
              {
                num: "02",
                icon: Target,
                title: "Get your projection",
                desc: "Our model compares you against 49K+ college players and projects your division fit."
              },
              {
                num: "03",
                icon: CheckCircle2,
                title: "Follow your goals",
                desc: "See which stats give you the most leverage — and track your progress toward them."
              }
            ].map((step, i) => (
              <FadeOnScroll key={i} delayMs={i * 150}>
                <div className="glass rounded-[2rem] p-6 shadow-soft h-full hover:-translate-y-1 transition-transform duration-300">
                  <div className="flex justify-between items-start mb-4">
                    <step.icon className="w-6 h-6 text-[var(--golden-sand)]" />
                    <span className="font-mono text-sm text-[var(--burnt-sienna)] font-bold">{step.num}</span>
                  </div>
                  <h3 className="text-lg font-semibold text-[var(--espresso)] mb-2 whitespace-pre-wrap">{step.title}</h3>
                  <p className="text-sm text-[var(--muted)] leading-relaxed">{step.desc}</p>
                </div>
              </FadeOnScroll>
            ))}
          </div>
        </section>

        {/* D. FEATURES */}
        <section id="features" className="py-24 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <h2 className="display-font text-3xl md:text-4xl text-center text-[var(--espresso)] font-bold mb-16">
              Everything a recruit actually needs.
            </h2>
          </FadeOnScroll>
          <div className="grid md:grid-cols-2 gap-6">

            <FadeOnScroll delayMs={0}>
              <div className="glass rounded-[2rem] p-6 shadow-soft h-full flex flex-col justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-[var(--espresso)] mb-2">Know Where You Fit</h3>
                  <p className="text-sm text-[var(--muted)] leading-relaxed mb-8">
                    See exactly where your stats project — from D1 powerhouses to D3 programs. No guessing, no generic advice.
                  </p>
                </div>
                <div className="bg-[var(--parchment)] rounded-2xl p-4 border border-[var(--stroke)] h-44 relative overflow-hidden flex items-center justify-center">
                  <DiagnosticShuffler />
                </div>
              </div>
            </FadeOnScroll>

            <FadeOnScroll delayMs={150}>
              <div className="glass rounded-[2rem] p-6 shadow-soft h-full flex flex-col justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-[var(--espresso)] mb-2">Improve What Matters</h3>
                  <p className="text-sm text-[var(--muted)] leading-relaxed mb-8">
                    Our model finds the stats that move your projection most — then tracks your progress week by week.
                  </p>
                </div>
                <div className="bg-[var(--walnut)] rounded-2xl p-4 border border-[var(--espresso)] h-44 relative overflow-hidden">
                  <TelemetryTypewriter />
                </div>
              </div>
            </FadeOnScroll>

          </div>
        </section>

        {/* E. PHILOSOPHY / MANIFESTO */}
        <section className="py-32 px-6 bg-[var(--walnut)] relative overflow-hidden">
          <div className="max-w-4xl mx-auto text-center relative z-10">
            <FadeOnScroll>
              <p className="text-lg text-[var(--warm-cream)]/60 mb-6 font-medium">Most recruiting tools focus on: <strong className="text-white">exposure. Showcases. Hype.</strong></p>
              <h2 className="display-font text-3xl md:text-5xl text-white font-bold leading-tight">
                We focus on: <span className="text-[var(--golden-sand)] italic font-medium">clarity.</span><br />
                A real projection. A plan that makes sense.
              </h2>
              <p className="text-xl text-[var(--warm-cream)]/80 italic mt-12 font-medium relative inline-block">
                <span className="absolute -left-4 top-0 text-[var(--golden-sand)] text-3xl opacity-40">&quot;</span>
                Recruiting clarity shouldn&apos;t be a luxury — it should be the standard.
                <span className="absolute -right-4 bottom-0 text-[var(--golden-sand)] text-3xl opacity-40">&quot;</span>
              </p>
            </FadeOnScroll>
          </div>
        </section>

        {/* F. TRUST BUILDERS */}
        <section className="py-24 px-6 max-w-6xl mx-auto">
          <div className="grid md:grid-cols-[1fr_1.2fr] gap-12 items-center">
            <FadeOnScroll>
              <div>
                <h2 className="display-font text-3xl md:text-4xl text-[var(--espresso)] font-bold mb-6">Built by Recruits</h2>
                <div className="relative pl-6 border-l-2 border-[var(--copper)]">
                  <p className="text-lg text-[var(--muted)] leading-relaxed italic">
                    &quot;BaseballPath was built by a former recruit who went through the process — and saw how broken it was. No clear projections. No data. Just opinions.&quot;
                  </p>
                </div>
              </div>
            </FadeOnScroll>

            <div className="grid grid-cols-2 gap-4">
              {[
                { val: "49,000+", lbl: "College player profiles in our dataset" },
                { val: "D1 → D3", lbl: "Full division coverage, not just the top" },
                { val: "< 2 min", lbl: "To get your first projection" },
                { val: "Real data", lbl: "Not opinions. Not rankings. Outcomes." }
              ].map((m, i) => (
                <FadeOnScroll key={i} delayMs={i * 100}>
                  <div className="glass rounded-2xl p-5 shadow-soft border border-[var(--clay-mist)]">
                    <p className="font-mono text-xl md:text-2xl font-bold text-[var(--walnut)] mb-2">{m.val}</p>
                    <p className="text-xs text-[var(--muted)] leading-tight">{m.lbl}</p>
                  </div>
                </FadeOnScroll>
              ))}
            </div>
          </div>
        </section>

        {/* G. PRICING */}
        <section id="pricing" className="py-24 px-6 max-w-6xl mx-auto">
          <FadeOnScroll>
            <h2 className="display-font text-3xl md:text-4xl text-center text-[var(--espresso)] font-bold mb-16">
              Start free. Upgrade when you&apos;re ready.
            </h2>
          </FadeOnScroll>
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto items-center">

            <FadeOnScroll delayMs={0}>
              <div className="glass rounded-[2rem] p-8 shadow-soft flex flex-col h-full">
                <h3 className="text-xl font-bold text-[var(--espresso)] mb-2">Starter</h3>
                <p className="text-3xl font-bold text-[var(--walnut)] mb-6 font-mono">Free</p>
                <div className="flex-grow">
                  <ul className="space-y-4 mb-8 text-sm text-[var(--muted)]">
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> 1 evaluation</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Division projection</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Basic school list</li>
                  </ul>
                </div>
                <Link href="/signup" className="block w-full text-center rounded-full border border-[var(--stroke)] px-6 py-3 font-semibold text-[var(--walnut)] hover:bg-[var(--stroke)]/20 transition-colors mt-auto">Start free</Link>
              </div>
            </FadeOnScroll>

            <FadeOnScroll delayMs={150}>
              <div className="glass rounded-[2.5rem] p-8 shadow-strong ring-2 ring-[var(--golden-sand)] relative transform md:scale-105 bg-[var(--parchment)] z-10 flex flex-col h-full">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[var(--golden-sand)] text-[var(--espresso)] font-bold uppercase tracking-widest text-[10px] px-3 py-1 rounded-full whitespace-nowrap">Most Popular</div>
                <h3 className="text-xl font-bold text-[var(--espresso)] mb-2">Pro</h3>
                <p className="text-3xl font-bold text-[var(--walnut)] mb-6 font-mono">$19<span className="text-base text-[var(--muted)] font-sans font-normal">/mo</span></p>
                <div className="flex-grow">
                  <ul className="space-y-4 mb-8 text-sm text-[var(--espresso)] font-medium">
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Unlimited evaluations</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Full school rankings</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Leverage-based goals</li>
                  </ul>
                </div>
                <Link href="/signup?plan=pro" className="block w-full text-center bg-[var(--burnt-sienna)] text-white rounded-full px-6 py-3 font-semibold shadow-soft hover:scale-[1.03] transition-transform mt-auto">Go Pro</Link>
              </div>
            </FadeOnScroll>

            <FadeOnScroll delayMs={300}>
              <div className="glass rounded-[2rem] p-8 shadow-soft flex flex-col h-full">
                <h3 className="text-xl font-bold text-[var(--espresso)] mb-2">Elite</h3>
                <p className="text-3xl font-bold text-[var(--walnut)] mb-6 font-mono">$49<span className="text-base text-[var(--muted)] font-sans font-normal">/mo</span></p>
                <div className="flex-grow">
                  <ul className="space-y-4 mb-8 text-sm text-[var(--muted)]">
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Everything in Pro</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Priority model access</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Advanced analytics</li>
                    <li className="flex gap-2"><CheckCircle2 className="w-4 h-4 text-[var(--sage-green)] shrink-0" /> Coach outreach templates</li>
                  </ul>
                </div>
                <Link href="/signup?plan=elite" className="block w-full text-center rounded-full bg-[var(--burnt-sienna)] text-white px-6 py-3 font-semibold shadow-soft hover:scale-[1.03] transition-transform mt-auto">Go Elite</Link>
              </div>
            </FadeOnScroll>

          </div>
        </section>

        {/* H. FINAL CTA */}
        <section className="py-32 px-6 text-center relative overflow-hidden">
          <div className="absolute inset-x-0 bottom-0 h-[600px] bg-[radial-gradient(ellipse_at_bottom,rgba(212,168,67,0.1),transparent_70%)] pointer-events-none"></div>
          <div className="max-w-xl mx-auto relative z-10">
            <FadeOnScroll>
              <h2 className="display-font text-5xl md:text-6xl text-[var(--espresso)] font-bold mb-4">
                Your projection is waiting.
              </h2>
              <p className="text-lg text-[var(--muted)] mb-10">
                Two minutes. Real data. <span className="text-[var(--burnt-sienna)] italic font-semibold">No credit card.</span>
              </p>
              <Link
                href={isAuthenticated ? "/dashboard" : "/predict"}
                className="inline-block overflow-hidden relative group bg-[var(--burnt-sienna)] text-[var(--warm-cream)] rounded-full px-10 py-4 text-lg font-semibold shadow-strong hover:scale-105 transition-transform duration-300"
              >
                <span className="relative z-10">Check my projection &rarr;</span>
                <span className="absolute inset-0 bg-[var(--primary-dark)] translate-y-full group-hover:translate-y-0 transition-transform duration-400 ease-out z-0"></span>
              </Link>
              <p className="text-sm text-[var(--muted)] mt-6 font-medium">
                Join 200+ recruits already using BaseballPath
              </p>
            </FadeOnScroll>
          </div>
        </section>

      </main>

      {/* I. FOOTER */}
      <footer className="bg-[var(--espresso)] text-[var(--warm-cream)] rounded-t-[4rem] px-6 pt-20 pb-10 mx-auto w-full relative z-20 overflow-hidden">
        <div className="max-w-6xl mx-auto grid md:grid-cols-4 gap-12 mb-16">
          <div className="col-span-1 md:col-span-1">
            <h3 className="text-sm uppercase tracking-[0.3em] font-semibold text-white/90 mb-4">BaseballPath</h3>
            <p className="text-white/60 text-sm">AI-powered recruiting clarity.</p>
          </div>
          <div>
            <h4 className="text-[var(--golden-sand)] text-xs uppercase tracking-widest font-bold mb-4">Product</h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li><Link href="#how-it-works" className="hover:text-white transition-colors">How It Works</Link></li>
              <li><Link href="#features" className="hover:text-white transition-colors">Features</Link></li>
              <li><Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[var(--golden-sand)] text-xs uppercase tracking-widest font-bold mb-4">Company</h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li><Link href="/about" className="hover:text-white transition-colors">About</Link></li>
              <li><Link href="/privacy" className="hover:text-white transition-colors">Privacy</Link></li>
              <li><Link href="/terms" className="hover:text-white transition-colors">Terms</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-[var(--golden-sand)] text-xs uppercase tracking-widest font-bold mb-4">Connect</h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li><a href="#" className="hover:text-white transition-colors">Twitter / X</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Instagram</a></li>
            </ul>
          </div>
        </div>

        <div className="max-w-6xl mx-auto border-t border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-white/40">
          <p>&copy; 2026 BaseballPath. All rights reserved.</p>
          <div className="flex items-center gap-2 bg-[var(--walnut)]/50 px-3 py-1.5 rounded-full border border-[var(--golden-sand)]/20">
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--sage-green)] shadow-[0_0_8px_var(--sage-green)] animate-pulse"></div>
            <span className="font-mono tracking-wider text-white/60">System Operational</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Extract mini components
function DiagnosticShuffler() {
  const data = [
    { school: "Arizona State", div: "D1", prob: "34%" },
    { school: "Cal Poly", div: "D1", prob: "61%" },
    { school: "Sonoma State", div: "D2", prob: "82%" }
  ];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((n) => (n + 1) % data.length);
    }, 3000);
    return () => clearInterval(timer);
  }, [data.length]);

  return (
    <div className="relative w-full max-w-[220px] h-[86px]">
      {data.map((item, i) => {
        const isActive = i === index;
        const offset = isActive ? 0 : 40;
        const opacity = isActive ? 1 : 0;
        const zIndex = isActive ? 10 : 0;

        return (
          <div
            key={i}
            className="absolute inset-0 bg-white rounded-2xl shadow-soft border border-[var(--stroke)] p-4 flex flex-col justify-center items-center"
            style={{
              transform: `translateY(${offset}px) scale(${isActive ? 1 : 0.95})`,
              opacity,
              zIndex,
              transition: "all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)"
            }}
          >
            <p className="font-bold text-sm text-[var(--espresso)]">{item.school}</p>
            <div className="flex gap-2 items-center mt-1">
              <span className="text-[10px] bg-[var(--sand)] px-1.5 py-0.5 rounded font-bold text-[var(--navy)]">{item.div}</span>
              <span className="text-xs font-bold text-[var(--burnt-sienna)]">{item.prob}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const TELEMETRY_MESSAGES = [
  "→ 60yd: 6.92s → target 6.78s (D1 median)",
  "→ Exit velo +3mph unlocks 12% probability gain",
  "→ 3 of 5 leverage stats on track this month"
];

function TelemetryTypewriter() {
  const [msgIdx, setMsgIdx] = useState(0);
  const [charIdx, setCharIdx] = useState(0);

  useEffect(() => {
    if (charIdx < TELEMETRY_MESSAGES[msgIdx].length) {
      const timer = setTimeout(() => {
        setCharIdx(n => n + 1);
      }, 50);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        setCharIdx(0);
        setMsgIdx((n) => (n + 1) % TELEMETRY_MESSAGES.length);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [charIdx, msgIdx]);

  return (
    <div className="font-mono text-[11px] sm:text-[13px] text-[var(--sage-green)] h-full overflow-hidden p-2 relative flex flex-col justify-center">
      <div className="text-[var(--warm-cream)]/40 text-[10px] uppercase mb-4 absolute top-2 left-2">System Telemetry Active</div>
      <div className="text-[var(--golden-sand)] leading-relaxed px-1">
        {TELEMETRY_MESSAGES[msgIdx].slice(0, charIdx)}
        <span className="inline-block w-2 bg-[var(--burnt-sienna)] h-3 ml-1 animate-pulse align-middle"></span>
      </div>
    </div>
  );
}

function CursorProtocol() {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setPhase((p) => (p + 1) % 4);
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative w-full h-full flex items-center justify-center pointer-events-none">
      <div className="relative w-40 h-24" style={{ perspective: "1000px" }}>
        <div
          className="w-full h-full relative"
          style={{
            transformStyle: "preserve-3d",
            transform: phase === 2 || phase === 3 ? "rotateY(180deg)" : "rotateY(0deg)",
            transition: "transform 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)"
          }}
        >
          <div className="absolute inset-0 bg-white rounded-xl shadow-sm border border-[var(--stroke)] flex flex-col justify-center items-center" style={{ backfaceVisibility: "hidden" }}>
            <div className={`bg-[var(--burnt-sienna)] text-white px-4 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1 transition-transform ${phase === 1 ? "scale-95" : "scale-100"}`}>
              <Share2 size={12} /> Share
            </div>
          </div>

          <div className="absolute inset-0 bg-[var(--walnut)] rounded-xl shadow-sm border border-[var(--golden-sand)]/30 p-2" style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}>
            <div className="flex gap-2 h-full">
              <div className="w-8 h-full bg-gradient-to-b from-white/10 to-transparent rounded"></div>
              <div className="flex-1 space-y-1.5 py-1">
                <div className="h-2 bg-white/20 rounded-full w-full"></div>
                <div className="h-2 bg-[var(--golden-sand)]/50 rounded-full w-2/3"></div>
                {phase === 3 && (
                  <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-[var(--sage-green)] text-white text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap opacity-100 transition-opacity">Link copied!</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <MousePointer2
        className="absolute text-[var(--burnt-sienna)] drop-shadow-md w-6 h-6 z-10"
        style={{
          transform: phase === 0 ? "translate(30px, 30px)" : "translate(0px, 5px)",
          opacity: phase >= 2 ? 0 : 1,
          transition: "all 0.5s ease-out"
        }}
        fill="white"
      />
    </div>
  );
}
