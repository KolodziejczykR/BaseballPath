"use client"

import Image from "next/image"
import { useState } from "react"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export const dynamic = "force-dynamic"

export default function WaitlistPage() {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [highSchoolYear, setHighSchoolYear] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const handleWaitlistSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (!email.trim()) {
      setError("Email is required")
      return
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address")
      return
    }

    setLoading(true)

    try {
      const response = await fetch(`${API_BASE_URL}/waitlist/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          name: name.trim(),
          high_school_year: highSchoolYear.trim(),
        }),
      })

      const data = await response.json()

      if (response.ok) {
        setSubmitted(true)
      } else {
        setError(data.detail || "Something went wrong. Please try again.")
      }
    } catch {
      setError("Network error. Please check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-xl border-b border-[var(--cool-stroke)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Image
              src="/BP-brown-logo-circle.png"
              alt="BaseballPath"
              width={40}
              height={40}
              className="h-10 w-10 rounded-full"
            />
            <p className="text-sm uppercase tracking-[0.28em] font-semibold text-[var(--cool-ink)]">
              BaseballPath
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 pt-12 md:pt-20 pb-12 md:pb-20">
        {/* Hero — Value Prop */}
        <div className="text-center max-w-3xl mx-auto mb-16 md:mb-20">
          <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--burnt-sienna)] font-semibold">
            Now in Beta
          </p>
          <h1 className="display-font text-5xl md:text-6xl lg:text-7xl leading-[1.05] font-semibold text-[var(--cool-ink)] mt-6 tracking-tight">
            Stop guessing.<br />
            Know your best-fit schools.
          </h1>
          <p className="mt-7 text-lg text-[var(--cool-ink-muted)] max-w-xl mx-auto leading-relaxed">
            Coaches recruit with data. Families usually recruit with guesswork.
            BaseballPath brings that data advantage to players and parents — so
            you can build a realistic target list and know what to work on next.
          </p>
        </div>

        {/* CTAs — Survey + Waitlist */}
        <div className="max-w-4xl mx-auto grid md:grid-cols-2 gap-8 mb-20 items-start">
          {/* Survey CTA */}
          <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-8 shadow-cool flex flex-col">
            <div>
              <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--burnt-sienna)] font-semibold mb-3">
                Help Us Build For You
              </p>
              <h2 className="display-font text-2xl md:text-3xl font-semibold text-[var(--cool-ink)] tracking-tight leading-tight">
                Shape what BaseballPath becomes
              </h2>
              <p className="mt-4 text-[var(--cool-ink-muted)] text-sm leading-relaxed">
                Take our 3-minute survey so we can build the features and pricing that actually
                make sense for you.
              </p>
            </div>
            <a
              href="https://forms.gle/dHKBJCTcMPzAAk3J8"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex items-center justify-center gap-2 rounded-full bg-[var(--burnt-sienna)] px-8 py-3.5 text-base font-semibold text-white shadow-cool transition-all duration-200 hover:-translate-y-0.5 hover:shadow-cool-strong"
            >
              Take the Survey
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </a>
          </div>

          {/* Waitlist CTA */}
          <div className="rounded-2xl border border-[var(--cool-stroke)] bg-white p-8 shadow-cool flex flex-col">
            <div className="text-center mb-6">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--burnt-sienna)] font-semibold mb-3">
                Be First In Line
              </p>
              <h2 className="display-font text-2xl md:text-3xl font-semibold text-[var(--cool-ink)] tracking-tight leading-tight">
                Join the waitlist
              </h2>
              <p className="mt-3 text-[var(--cool-ink-muted)] text-sm">
                Be first in line when we launch in May.
              </p>
              <div className="mt-5 inline-flex items-center gap-2 rounded-full bg-[var(--cool-surface-2)] border border-[var(--cool-stroke)] px-4 py-2">
                <svg className="w-4 h-4 text-[var(--burnt-sienna)]" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
                <span className="text-sm font-medium text-[var(--cool-ink)]">
                  3 members win a free account at launch
                </span>
              </div>
            </div>

            {submitted ? (
              <div className="text-center py-6">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-[var(--sage-green)]/15 mb-4">
                  <svg className="w-7 h-7 text-[var(--sage-green)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-[var(--espresso)]">
                  You&apos;re on the list!
                </h3>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Thank you for joining! We&apos;ll reach out before launch.
                </p>
              </div>
            ) : (
              <form onSubmit={handleWaitlistSubmit} className="space-y-4 max-w-sm mx-auto w-full">
                <div>
                  <input
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="form-control"
                  />
                </div>
                <div>
                  <input
                    type="text"
                    placeholder="Name (optional)"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="form-control"
                  />
                </div>
                <div>
                  <select
                    value={highSchoolYear}
                    onChange={(e) => setHighSchoolYear(e.target.value)}
                    className="form-control"
                  >
                    <option value="">Player HS Grad Year (optional)</option>
                    <option value="2026">2026</option>
                    <option value="2027">2027</option>
                    <option value="2028">2028</option>
                    <option value="2029">2029</option>
                    <option value="2030">2030</option>
                    <option value="2031+">2031+</option>
                  </select>
                </div>

                {error && (
                  <p className="text-sm text-red-600 text-center">{error}</p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-full bg-[var(--burnt-sienna)] px-6 py-3.5 text-base font-semibold text-white shadow-cool transition-all duration-200 hover:-translate-y-0.5 hover:shadow-cool-strong active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading && (
                    <svg className="animate-spin h-5 w-5 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  )}
                  {loading ? "Joining..." : "Join the Waitlist"}
                </button>

                <p className="text-xs text-[var(--muted)] text-center">
                  Free to join. No spam, ever.
                </p>
              </form>
            )}
          </div>
        </div>

        {/* Information Cards */}
        <div className="max-w-5xl mx-auto grid md:grid-cols-3 gap-6 mb-16">
          {/* Card 1 */}
          <div className="rounded-2xl bg-white p-8 shadow-cool border border-[var(--cool-stroke)] hover:-translate-y-1 transition-transform duration-300 flex flex-col">
            <h3 className="text-xl font-bold text-[var(--espresso)] mb-2 whitespace-pre-wrap">Metrics &rarr; Best-Fit Schools</h3>
            <p className="text-sm font-medium text-[var(--cool-ink-muted)] mb-6">
              Turn your measurables + preferences into a realistic target list in minutes.
            </p>
            <ul className="space-y-3 flex-grow mb-6">
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Uses real D1–D3 player data to estimate where you fit (not just dream schools).
              </li>
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Personalized by position + your key metrics (Exit Velo, FB Velo, 60 time, etc.)
              </li>
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Filters for what matters to you: location, academics, cost, school size, and more.
              </li>
            </ul>
            <p className="text-xs font-medium text-[var(--espresso)]/70 italic mt-auto border-t border-[var(--stroke)] pt-4">
              Just a clearer starting point for who you should contact, no more guessing and wasted time.
            </p>
          </div>

          {/* Card 2 */}
          <div className="rounded-2xl bg-white p-8 shadow-cool border border-[var(--cool-stroke)] hover:-translate-y-1 transition-transform duration-300 flex flex-col">
            <h3 className="text-xl font-bold text-[var(--espresso)] mb-2 whitespace-pre-wrap">Recruiting Guidance Without the Agency Price</h3>
            <p className="text-sm font-medium text-[var(--cool-ink-muted)] mb-6">
              Most families piece recruiting together from random advice. BaseballPath is built to make the process simple and affordable.
            </p>
            <ul className="space-y-3 flex-grow mb-6">
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                A step-by-step plan that tells you what to do at your stage (not generic tips).
              </li>
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Practical tools families actually need: curated school list, outreach, and checklists.
              </li>
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Built for players and parents who want clarity without paying thousands.
              </li>
            </ul>
            <p className="text-xs font-medium text-[var(--espresso)]/70 italic mt-auto border-t border-[var(--stroke)] pt-4">
              You stay in control, we just make the path obvious.
            </p>
          </div>

          {/* Card 3 */}
          <div className="rounded-2xl bg-white p-8 shadow-cool border border-[var(--cool-stroke)] hover:-translate-y-1 transition-transform duration-300 flex flex-col">
            <h3 className="text-xl font-bold text-[var(--espresso)] mb-2 whitespace-pre-wrap">Per-School Detail You Can Act On</h3>
            <p className="text-sm font-medium text-[var(--cool-ink-muted)] mb-6">
              Each school in your list comes with the context you need to make a real decision &mdash; not just a name.
            </p>
            <ul className="space-y-3 flex-grow mb-6">
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Conference, division, and roster context so you know the level you&apos;re looking at.
              </li>
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                A &quot;why this school&quot; narrative that ties your stats to the program&apos;s actual fit.
              </li>
              <li className="flex gap-3 items-start text-sm text-[var(--muted)]">
                <div className="w-1.5 h-1.5 rounded-full bg-[var(--golden-sand)] shrink-0 mt-1.5"></div>
                Academic match, annual cost, and how you compare to the division average.
              </li>
            </ul>
            <p className="text-xs font-medium text-[var(--espresso)]/70 italic mt-auto border-t border-[var(--stroke)] pt-4">
              Real evidence per school, not generic ranks.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-16 pb-8">
          <p className="text-xs text-[var(--muted)]">
            &copy; 2026 BaseballPath. All rights reserved.
          </p>
        </div>
      </main>
    </div>
  )
}
