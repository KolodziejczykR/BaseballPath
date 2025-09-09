"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Modal } from "@/components/ui/modal"
import { submitWaitlistEntry } from "@/lib/api"

// Force dynamic rendering to avoid build-time environment variable issues
export const dynamic = 'force-dynamic'

export default function DirectPostWaitlistSurvey() {
  const [email, setEmail] = useState("")
  const [playerType, setPlayerType] = useState("")
  const [highSchoolYear, setHighSchoolYear] = useState("")
  const [emailConsent, setEmailConsent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [showPrivacyModal, setShowPrivacyModal] = useState(false)
  const [privacyContent, setPrivacyContent] = useState("")
  const router = useRouter()

  useEffect(() => {
    // Check if email is verified
    const waitlistEmail = sessionStorage.getItem("waitlist_email")
    const isVerified = sessionStorage.getItem("waitlist_email_verified")
    
    if (!waitlistEmail || !isVerified) {
      // If no email or not verified, redirect to waitlist page
      window.location.href = "/waitlist"
      return
    }
    
    setEmail(waitlistEmail)
  }, [])

  const loadPrivacyPolicy = async () => {
    try {
      const response = await fetch('/api/privacy-policy')
      const data = await response.text()
      setPrivacyContent(data)
      setShowPrivacyModal(true)
    } catch (error) {
      console.error('Failed to load privacy policy:', error)
      // Fallback content if file can't be loaded
      setPrivacyContent("Privacy Policy is currently unavailable. Please contact support@baseballpath.com for more information.")
      setShowPrivacyModal(true)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Prevent double submission
    if (loading || submitted) {
      return
    }
    
    // Check if email is still available (not cleared from successful submission)
    if (!email) {
      alert("Session expired. Please start over from the waitlist page.")
      window.location.href = "/waitlist"
      return
    }
    
    // Validate required fields
    if (!playerType || !highSchoolYear || !emailConsent) {
      alert("Please complete all required fields and agree to receive emails.")
      return
    }
    
    setLoading(true)

    try {
      // Create complete waitlist entry with survey data
      const result = await submitWaitlistEntry({
        email,
        user_type: playerType,
        high_school_year: highSchoolYear,
        email_consent: emailConsent,
      })

      console.log('[API] Survey data saved:', result)
      
      // Store user data for later use in bonus survey
      if (result.id) {
        sessionStorage.setItem("waitlist_user_id", result.id)
        sessionStorage.setItem("waitlist_user_type", playerType)
        sessionStorage.setItem("waitlist_high_school_year", highSchoolYear)
      }
      
      setSubmitted(true)
      
      // Clear email from sessionStorage but keep user data
      sessionStorage.removeItem("waitlist_email")
    } catch (err) {
      console.error("Survey submission error:", err)
      
      // Handle specific error cases
      if (err instanceof Error && err.message.includes("already on our waitlist")) {
        alert("This email has already been submitted. You cannot submit the survey twice.")
        sessionStorage.removeItem("waitlist_email")
        window.location.href = "/waitlist/success"
        return
      }
      
      alert(err instanceof Error ? err.message : "There was an error saving your survey. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    // Redirect to success page (replace to clean up history)
    window.location.replace("/waitlist/success")
    return null
  }

  return (
    <div className="min-h-screen relative overflow-hidden font-sans" style={{ backgroundColor: '#03032d', fontFamily: 'var(--font-manrope)' }}>
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-blue-950/5"></div>
      

      {/* Header */}
      <header className="relative z-10 w-full">
        <div className="px-6 lg:px-8 py-8">
          <div className="flex items-center">
            <img 
              src="/logo-header.png"
              alt="BaseballPath"
              className="h-12 w-auto"
            />
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-2xl mx-auto px-6 lg:px-8 py-8">
        <div className="bg-white/5 backdrop-blur-sm rounded-3xl p-8 sm:p-12 border border-white/10">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-4">
              Two quick questions, and you’re in!
            </h1>
            
            <p className="text-lg text-white/70 leading-relaxed">
              We’ll tailor updates and notifications to your answers.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Player Type Question */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                I am a... <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <select
                value={playerType}
                onChange={(e) => setPlayerType(e.target.value)}
                className="w-full h-12 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm pl-4 pr-12 py-3 text-base text-white focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-purple-400"
              >
                <option value="" className="text-gray-900">Select one</option>
                <option value="parent" className="text-gray-900">Parent of a player</option>
                <option value="player" className="text-gray-900">Player</option>
              </select>
            </div>

            {/* High School Year Question */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                High school year <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <select
                value={highSchoolYear}
                onChange={(e) => setHighSchoolYear(e.target.value)}
                className="w-full h-12 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm pl-4 pr-12 py-3 text-base text-white focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-purple-400"
              >
                <option value="" className="text-gray-900">Select year</option>
                <option value="freshman" className="text-gray-900">Freshman</option>
                <option value="sophomore" className="text-gray-900">Sophomore</option>
                <option value="junior" className="text-gray-900">Junior</option>
                <option value="senior" className="text-gray-900">Senior</option>
              </select>
            </div>

            {/* Email Consent */}
            <div>
              <div className="flex items-start space-x-3">
                <input
                  type="checkbox"
                  id="email-consent"
                  checked={emailConsent}
                  onChange={(e) => setEmailConsent(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border border-white/20 bg-white/10 text-purple-600 focus:ring-purple-400"
                />
                <label htmlFor="email-consent" className="text-sm text-white/80 leading-relaxed">
                  I agree to receive emails from BaseballPath about the waitlist, launch updates, and recruiting tips. I can unsubscribe anytime.
                  By joining, I confirm I'm 13+ and agree to the{' '}
                  <button 
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      loadPrivacyPolicy()
                    }}
                    className="underline hover:text-white/60 transition-colors duration-200"
                    style={{ color: '#6b7ff2' }}
                  >
                    Privacy Policy
                  </button>
                  . <span style={{ color: '#6b7ff2' }}>*</span>
                </label>
              </div>
            </div>

            <Button 
              type="submit" 
              size="lg" 
              loading={loading}
              className="w-full text-lg py-4 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg hover:shadow-xl active:shadow-md"
              style={{ 
                backgroundColor: '#6b7ff2',
                borderColor: '#6b7ff2',
                boxShadow: '0 4px 14px 0 rgba(107, 127, 242, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
              }}
            >
              {loading ? "Joining..." : "Complete Signup"}
            </Button>
          </form>
        </div>
      </main>

      {/* Privacy Policy Modal */}
      <Modal
        isOpen={showPrivacyModal}
        onClose={() => setShowPrivacyModal(false)}
        title="BaseballPath Privacy Policy"
      >
        <div className="space-y-4 text-sm">
          <pre className="whitespace-pre-wrap font-sans">{privacyContent}</pre>
        </div>
      </Modal>
    </div>
  )
}