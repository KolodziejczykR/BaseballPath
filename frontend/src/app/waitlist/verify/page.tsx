"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"

// Force dynamic rendering to avoid build-time environment variable issues
export const dynamic = 'force-dynamic'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function VerifyEmailPage() {
  const [email, setEmail] = useState("")
  const [token, setToken] = useState(["", "", "", "", "", ""])
  const [loading, setLoading] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const router = useRouter()

  // Handle individual digit input
  const handleDigitChange = (index: number, value: string) => {
    // Only allow single digit
    if (value.length > 1) return
    
    // Only allow numbers
    if (value && !/^\d$/.test(value)) return
    
    const newToken = [...token]
    newToken[index] = value
    setToken(newToken)
    
    // Auto-focus next input if digit entered
    if (value && index < 5) {
      const nextInput = document.getElementById(`digit-${index + 1}`)
      nextInput?.focus()
    }
  }

  // Handle key events (backspace, etc.)
  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !token[index] && index > 0) {
      // If current field is empty and backspace pressed, go to previous field
      const prevInput = document.getElementById(`digit-${index - 1}`)
      prevInput?.focus()
    }
  }

  // Handle paste functionality
  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    
    if (pastedData.length <= 6) {
      const newToken = [...token]
      for (let i = 0; i < 6; i++) {
        newToken[i] = pastedData[i] || ""
      }
      setToken(newToken)
      
      // Focus the next empty field or the last field
      const nextEmptyIndex = newToken.findIndex(digit => digit === "")
      const targetIndex = nextEmptyIndex === -1 ? 5 : Math.min(nextEmptyIndex, 5)
      const targetInput = document.getElementById(`digit-${targetIndex}`)
      targetInput?.focus()
    }
  }

  useEffect(() => {
    // Get email from sessionStorage
    const waitlistEmail = sessionStorage.getItem("waitlist_email")
    if (waitlistEmail) {
      setEmail(waitlistEmail)
    } else {
      // If no email in session, redirect to waitlist page
      window.location.href = "/waitlist"
    }
  }, [])

  const handleVerifyToken = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (loading) return
    
    const tokenString = token.join("")
    if (tokenString.length !== 6) {
      setError("Please enter all 6 digits of your verification code.")
      return
    }
    
    setLoading(true)
    setError("")
    setMessage("")

    try {
      const response = await fetch(`${API_BASE_URL}/waitlist/verify-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          token: tokenString
        }),
      })

      const data = await response.json()

      if (response.ok && data.verified) {
        setMessage("Email verified successfully! Redirecting...")
        
        // Store verified email and redirect to survey
        sessionStorage.setItem("waitlist_email_verified", "true")
        setTimeout(() => {
          window.location.href = "/waitlist/direct_post_waitlist_survey"
        }, 1500)
      } else {
        setError(data.message || "Verification failed. Please try again.")
      }
      
    } catch (err) {
      console.error("Verification error:", err)
      setError("Network error. Please check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (resendLoading) return
    
    setResendLoading(true)
    setError("")
    setMessage("")

    try {
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
        setMessage("New verification code sent! Check your inbox.")
        setToken(["", "", "", "", "", ""]) // Clear all inputs
        // Focus first input
        const firstInput = document.getElementById("digit-0")
        firstInput?.focus()
      } else {
        setError(data.detail || "Failed to resend code. Please try again.")
      }
      
    } catch (err) {
      console.error("Resend error:", err)
      setError("Network error. Please try again.")
    } finally {
      setResendLoading(false)
    }
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
            <div className="w-20 h-20 rounded-full flex items-center justify-center mb-6 mx-auto" 
                 style={{ 
                   backgroundColor: '#6b7ff2',
                   boxShadow: '0 4px 20px rgba(107, 127, 242, 0.4)'
                 }}>
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
              </svg>
            </div>
            
            <h1 className="text-3xl font-bold text-white mb-4">
              Check Your Email
            </h1>
            
            <p className="text-lg text-white/70 leading-relaxed mb-2">
              We sent a 6-digit verification code to:
            </p>
            
            <p className="text-lg font-semibold text-white mb-4">
              {email}
            </p>
            
            <p className="text-sm text-white/60">
              Enter the code below to continue (expires in 10 minutes)
            </p>
          </div>

          <form onSubmit={handleVerifyToken} className="space-y-6">
            {/* Verification Code Input */}
            <div>
              <label className="block text-lg font-semibold text-white mb-6 text-center">
                Verification Code
              </label>
              <div className="flex justify-center space-x-3 mb-4">
                {token.map((digit, index) => (
                  <input
                    key={index}
                    id={`digit-${index}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleDigitChange(index, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(index, e)}
                    onPaste={handlePaste}
                    className="w-14 h-14 rounded-full border-2 border-white/20 bg-white/10 backdrop-blur-sm text-center text-2xl font-bold text-white focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-purple-400 transition-all duration-200"
                    style={{ 
                      caretColor: 'transparent' // Hide cursor for cleaner look
                    }}
                  />
                ))}
              </div>
              <p className="text-center text-white/50 text-sm">
                Enter the 6-digit code sent to your email
              </p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
                <p className="text-red-400 text-center font-medium">{error}</p>
              </div>
            )}

            {/* Success Message */}
            {message && (
              <div className="p-4 bg-emerald-500/20 border border-emerald-500/30 rounded-lg">
                <p className="text-emerald-400 text-center font-medium">{message}</p>
              </div>
            )}

            <Button 
              type="submit" 
              size="lg" 
              loading={loading}
              className="w-full text-lg py-4 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg hover:shadow-xl"
              style={{ 
                backgroundColor: '#6b7ff2',
                borderColor: '#6b7ff2',
                boxShadow: '0 4px 14px 0 rgba(107, 127, 242, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
              }}
            >
              {loading ? "Verifying..." : "Verify Code"}
            </Button>

            {/* Resend Code */}
            <div className="text-center pt-4">
              <p className="text-white/60 text-sm mb-3">Didn't receive the code?</p>
              <button
                type="button"
                onClick={handleResendCode}
                disabled={resendLoading}
                className="text-purple-400 hover:text-purple-300 font-medium text-sm underline transition-colors duration-200 disabled:opacity-50"
              >
                {resendLoading ? "Sending..." : "Resend Code"}
              </button>
            </div>

            {/* Back to waitlist */}
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => {
                  sessionStorage.removeItem("waitlist_email")
                  window.location.href = "/waitlist"
                }}
                className="text-white/50 hover:text-white/70 text-sm transition-colors duration-200"
              >
                ← Back to Waitlist
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}