"use client"

import { useState } from "react"

// Force dynamic rendering to avoid build-time environment variable issues
export const dynamic = 'force-dynamic'
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { validateEmail, checkEmailExists } from "@/lib/api"

export default function WaitlistPage() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const router = useRouter()

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
      // Check if email already exists
      const emailExists = await checkEmailExists(email)
      if (emailExists) {
        setError("This email is already on our waitlist!")
        return
      }

      // Store email in sessionStorage for survey page (don't save to DB yet)
      sessionStorage.setItem("waitlist_email", email)
      
      // Redirect to survey page
      router.push("/waitlist/survey")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      {/* Header */}
      <header className="w-full bg-white shadow-sm border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-red-600 bg-clip-text text-transparent">
              BaseballPATH
            </h1>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center space-y-6">
          {/* Hero Section */}
          <div className="space-y-4">
            <h2 className="text-6xl sm:text-5xl font-bold text-gray-900 leading-tight">
              The AI That {" "}
              <span className="bg-gradient-to-r from-blue-600 to-rose-600 bg-clip-text text-transparent">
                Gets You Recruited
              </span>
            </h2>
            
            <p className="text-lg sm:text-lg text-gray-600 max-w-3xl mx-auto leading-relaxed">
              <span className="bg-clip-text font-bold text-gray-900 leading-tight">Trusted by coaches. Built by players. Powered by AI. </span> 
              After interviewing coaches across the country and living the recruiting struggle ourselves, <span className="bg-clip-text font-bold text-gray-900 leading-tight"> we built the solution. </span> 
              Join the waitlist below and get entered into our launch giveaway! 
            </p>
            <p className="text-lg sm:text-lg text-gray-600 max-w-3xl mx-auto leading-relaxed">
              <span className="bg-gradient-to-r from-emerald-500 to-teal-500 bg-clip-text text-transparent font-bold"> Five lucky waitlist members get BaseballPATH completely free on launch day.</span>
            </p>
          </div>

          {/* Email Form */}
          <div className="max-w-md mx-auto">
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                type="email"
                placeholder="Enter your email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={error}
                className="text-center text-lg"
              />
              
              <Button 
                type="submit" 
                size="lg" 
                loading={loading}
                className="w-full text-lg py-4"
              >
                {loading ? "Joining Waitlist..." : "Reserve Your Spot"}
              </Button>
              
              <p className="text-xs text-gray-500 font-bold italic mt-2">
                No purchase necessary • Winners drawn at launch • 100% free to enter
              </p>
            </form>
          </div>

          {/* Benefits */}
          <div className="pt-8 grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Supercharge your recruitment
              </h3>
              <p className="text-gray-600 leading-relaxed text-sm">
                Get data driven insights that show exactly which schools are your best fit.
              </p>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300">
              <div className="w-10 h-10 bg-gradient-to-r from-red-500 to-red-600 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Shift your focus to development
              </h3>
                <p className="text-gray-600 leading-relaxed text-sm">
                While you focus on becoming a better player, others stress over finding college matches.       
                </p>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300">
              <div className="w-10 h-10 bg-gradient-to-r from-gray-700 to-gray-800 rounded-lg flex items-center justify-center mb-4 mx-auto">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Don&apos;t miss the giveaway
              </h3>
              <p className="text-gray-600 leading-relaxed text-sm">
                Join the waitlist for free, get entered automatically. It&apos;s that simple.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}