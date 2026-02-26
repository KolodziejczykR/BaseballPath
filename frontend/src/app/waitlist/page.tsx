"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Modal } from "@/components/ui/modal"
import { validateEmail } from "@/lib/api"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Force dynamic rendering to avoid build-time environment variable issues
export const dynamic = 'force-dynamic'

export default function WaitlistPage() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [showRulesModal, setShowRulesModal] = useState(false)
  const [rulesContent, setRulesContent] = useState("")
  const router = useRouter()

  const loadRules = async () => {
    try {
      const response = await fetch('/api/giveaway-terms')
      const data = await response.text()
      setRulesContent(data)
      setShowRulesModal(true)
    } catch (error) {
      console.error('Failed to load rules:', error)
      // Fallback content if file can't be loaded
      setRulesContent("Official Rules are currently unavailable. Please contact support@baseballpath.com for more information.")
      setShowRulesModal(true)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (!email) {
      setError("Email is required")
      return
    }

    const isValidEmail = await validateEmail(email)
    if (!isValidEmail) {
      setError("Please enter a valid email address")
      return
    }

    setLoading(true)

    try {
      // Send verification email
      const response = await fetch(`${API_BASE_URL}/waitlist/send-verification`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email
        }),
      })

      const data = await response.json()

      if (response.ok) {
        // Store email in sessionStorage for verification page
        sessionStorage.setItem("waitlist_email", email)
        
        // Redirect to verification page
        router.push("/waitlist/verify")
      } else {
        setError(data.detail || "Failed to send verification email. Please try again.")
      }
    } catch (err) {
      console.error("Email verification error:", err)
      setError("Network error. Please check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 backdrop-blur-md border-b border-black/5">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-[var(--navy)] text-white grid place-items-center font-semibold">
              BP
            </div>
            <div className="leading-tight">
              <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">BaseballPath</p>
              <p className="text-base font-semibold">Recruiting OS</p>
            </div>
          </div>
          <nav className="hidden items-center gap-8 text-sm font-medium text-[var(--muted)] md:flex">
            <Link href="/" className="hover:text-[var(--foreground)]">Home</Link>
            <Link href="/plans" className="hover:text-[var(--foreground)]">Plans</Link>
            <Link href="/login" className="text-[var(--foreground)]">Login</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-8">
            <div className="space-y-4">
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Waitlist</p>
              <h1 className="display-font text-4xl md:text-5xl leading-tight">
                Cut the research. Save 100+ hours and get your top college fits in minutes.
              </h1>
              <p className="text-lg text-[var(--muted)]">
                Enter your metrics and preferences. BaseballPath returns a ranked list of
                programs where you’re most likely to succeed—across all divisions.
              </p>
            </div>

            <div className="glass rounded-3xl p-6 shadow-soft">
              <p className="text-sm uppercase tracking-[0.3em] text-[var(--muted)]">Launch Giveaway</p>
              <h3 className="mt-3 text-2xl font-semibold">
                Win a BaseballPath account for free.
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Join the waitlist to enter automatically. 5 winners • ARV $250 each.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {[
                {
                  title: "Your college matches",
                  desc: "A personalized list of schools that match your metrics and goals.",
                },
                {
                  title: "Save time, decide faster",
                  desc: "Get a clear target list in minutes, not months.",
                },
                {
                  title: "Built on your data",
                  desc: "We score fit using your actual measurables and preferences.",
                },
              ].map((item) => (
                <div key={item.title} className="glass rounded-2xl p-5 shadow-soft">
                  <p className="text-lg font-semibold">{item.title}</p>
                  <p className="mt-2 text-sm text-[var(--muted)]">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="glass shadow-strong rounded-3xl p-8 h-fit">
            <h2 className="text-xl font-semibold">Join the waitlist</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Early access + giveaway entry. Free to join.
            </p>
            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={error}
                className="text-base py-3 bg-white border-[var(--stroke)] text-[var(--foreground)]"
              />

              <Button
                type="submit"
                size="lg"
                loading={loading}
                className="w-full text-base py-3 font-semibold shadow-strong"
                style={{
                  backgroundColor: "var(--primary)",
                  borderColor: "var(--primary)",
                }}
              >
                {loading ? "Joining Waitlist..." : "Get on the Waitlist (Free)"}
              </Button>

              <p className="text-xs text-[var(--muted)]">
                No purchase necessary • Winners selected at random and notified by email • Odds depend on number of entries •{" "}
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    loadRules()
                  }}
                  className="underline hover:text-[var(--foreground)] transition-colors duration-200"
                >
                  Official Rules
                </button>
              </p>
            </form>
          </div>
        </div>
      </main>

      {/* Official Rules Modal */}
      <Modal
        isOpen={showRulesModal}
        onClose={() => setShowRulesModal(false)}
        title="BaseballPath Launch Giveaway Official Rules"
      >
        <div className="space-y-4 text-sm">
          <pre className="whitespace-pre-wrap font-sans">{rulesContent}</pre>
        </div>
      </Modal>
    </div>
  )
}
