"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
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
    <div className="min-h-screen relative overflow-hidden" style={{ backgroundColor: '#03032d' }}>
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-blue-950/5"></div>
      
      {/* Background logo - animated fade in/out at different spots */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <img 
          src="/background-logo.png"
          alt=""
          className="absolute w-[1200%] h-auto"
          style={{ 
            animation: 'logoSpots 18s ease-in-out infinite',
            opacity: 0,
            left: '0%',
            top: '15%'
          }}
        />
      </div>
      
      <style jsx>{`
        @keyframes logoSpots {
          0%, 18% {
            opacity: 0;
            left: 0%;
            top: 15%;
          }
          4%, 14% {
            opacity: 0.1;
            left: 0%;
            top: 15%;
          }
          20%, 38% {
            opacity: 0;
            left: -15%;
            top: 0%;
          }
          24%, 34% {
            opacity: 0.1;
            left: -15%;
            top: 0%;
          }
          40%, 58% {
            opacity: 0;
            left: 60%;
            top: -15%;
          }
          44%, 54% {
            opacity: 0.1;
            left: 60%;
            top: -15%;
          }
          60%, 78% {
            opacity: 0;
            left: 5%;
            top: 28%;
          }
          64%, 74% {
            opacity: 0.1;
            left: 5%;
            top: 28%;
          }
          80%, 98% {
            opacity: 0;
            left: 50%;
            top: 32%;
          }
          84%, 94% {
            opacity: 0.1;
            left: 50%;
            top: 32%;
          }
          100% {
            opacity: 0;
            left: 0%;
            top: 15%;
          }
        }
      `}</style>

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

      {/* Main Content */}
      <main className="relative z-10 max-w-4xl mx-auto px-6 lg:px-8 py-8">
        <div className="text-center space-y-8">
          {/* Hero Section */}
          <div className="space-y-8">
            <div className="space-y-4">
              <h1 className="text-4xl lg:text-4xl font-bold text-white leading-tight tracking-tight">
                Cut the research. Save <span style={{ color: '#6b7ff2' }}>100+ hours, </span> 
                and see your top personalized college picks <span style={{ color: '#6b7ff2' }}>in minutes.</span>
              </h1>
            </div>
            
            <div className="max-w-2xl mx-auto space-y-4">
              <p className="text-xl font-semibold text-white">
                Built by players. Powered by AI.
              </p>
              <p className="text-lg text-white/75 leading-relaxed font-semibold">
                Enter basic metrics like exit velocity and 60-yard dash time, as well as your college preferences. 
                BaseballPath analyzes your profile and returns a list of programs where you’ll find your dream school, across all divisions.              
              </p>
            </div>
          </div>

          {/* Giveaway Section */}
          <div className="bg-gradient-to-r from-purple-900/40 to-blue-900/40 rounded-2xl p-6 border border-white/10 backdrop-blur-sm">
            <div className="space-y-3">
              <h3 className="text-xl font-bold text-white">
                Launch Giveaway • Win a BaseballPath account for free! 🎉
              </h3>
              <p className="text-base text-white/80">
                Join the waitlist to enter automatically! 5 winners • ARV $250 each
              </p>
            </div>
          </div>

          {/* Email Form */}
          <div className="max-w-sm mx-auto">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="relative">
                <Input
                  type="email"
                  placeholder="Enter your email to join the waitlist"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  error={error}
                  className="text-center text-base py-3 bg-white/10 border-white/20 text-white placeholder:text-white/50 backdrop-blur-sm"
                  style={{
                    '--autofill-bg': 'rgba(255, 255, 255, 0.1)',
                    '--autofill-text': '#ffffff'
                  } as React.CSSProperties}
                />
              </div>
              
              <Button 
                type="submit" 
                size="lg" 
                loading={loading}
                className="w-full text-base py-3 font-semibold transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg hover:shadow-xl active:shadow-md"
                style={{ 
                  backgroundColor: '#6b7ff2',
                  borderColor: '#6b7ff2',
                  boxShadow: '0 4px 14px 0 rgba(107, 127, 242, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
                }}
              >
                {loading ? "Joining Waitlist..." : "Get on the Waitlist (Free)"}
              </Button>
              
              <p className="text-xs text-white/50 font-medium">
                No purchase necessary • Winners selected at random and notified by email • Odds depend on number of entries • {' '}
                <button 
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    loadRules()
                  }}
                  className="underline hover:text-white/70 transition-colors duration-200"
                >
                  Official Rules
                </button>
              </p>
            </form>
          </div>

          {/* Benefits Grid */}
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            <div className="group bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-purple-400/30 transition-all duration-200 hover:bg-white/8 hover:shadow-lg cursor-pointer transform hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 mx-auto transition-all duration-200 group-hover:scale-105 shadow-md"
                   style={{ 
                     backgroundColor: '#6b7ff2',
                     boxShadow: '0 4px 12px rgba(107, 127, 242, 0.3)'
                   }}>
                <svg className="w-6 h-6 text-white transition-transform duration-200 group-hover:rotate-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-3 group-hover:text-purple-200 transition-colors duration-200">
                Your college matches
              </h3>
              <p className="text-white/60 leading-relaxed text-sm group-hover:text-white/75 transition-colors duration-200">
                A personalized list of top colleges that match your metrics, academics, and preferences, so you know exactly where to focus.
              </p>
            </div>

            <div className="group bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-purple-400/30 transition-all duration-200 hover:bg-white/8 hover:shadow-lg cursor-pointer transform hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 mx-auto transition-all duration-200 group-hover:scale-105 shadow-md"
                   style={{ 
                     backgroundColor: '#6b7ff2',
                     boxShadow: '0 4px 12px rgba(107, 127, 242, 0.3)'
                   }}>
                <svg className="w-6 h-6 text-white transition-transform duration-200 group-hover:rotate-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-3 group-hover:text-purple-200 transition-colors duration-200">
                Save time, decide faster
              </h3>
              <p className="text-white/60 leading-relaxed text-sm group-hover:text-white/75 transition-colors duration-200">
                Families spend ~100 hours researching potential college options. Get a clear target list in minutes and move forward with confidence.
              </p>
            </div>

            <div className="group bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-purple-400/30 transition-all duration-200 hover:bg-white/8 hover:shadow-lg cursor-pointer transform hover:-translate-y-1">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 mx-auto transition-all duration-200 group-hover:scale-105 shadow-md"
                   style={{ 
                     backgroundColor: '#4d61b5',
                     boxShadow: '0 4px 12px rgba(77, 97, 181, 0.3)'
                   }}>
                <svg className="w-6 h-6 text-white transition-transform duration-200 group-hover:-rotate-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-3 group-hover:text-purple-200 transition-colors duration-200">
                Built on your data
              </h3>
              <p className="text-white/60 leading-relaxed text-sm group-hover:text-white/75 transition-colors duration-200">
                We use your actual metrics, as well as what matters most to you in a college, to match you with the right programs.
              </p>
            </div>
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