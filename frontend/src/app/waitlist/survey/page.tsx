"use client"

import { useState, useEffect } from "react"

// Force dynamic rendering to avoid build-time environment variable issues
export const dynamic = 'force-dynamic'
import { Button } from "@/components/ui/button"
import { submitWaitlistEntry } from "@/lib/api"

export default function WaitlistSurvey() {
  const [email, setEmail] = useState("")
  const [recruitingChallenge, setRecruitingChallenge] = useState("")
  const [budget, setBudget] = useState("")
  const [travelTeam, setTravelTeam] = useState("")
  const [recruitingAgency, setRecruitingAgency] = useState("")
  const [additionalInfo, setAdditionalInfo] = useState("")
  const [desiredFeatures, setDesiredFeatures] = useState("")
  const [graduationYear, setGraduationYear] = useState("")
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)

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
    if (!budget || !travelTeam || !recruitingAgency || !graduationYear) {
      alert("Please answer all required questions before submitting.")
      return
    }
    
    setLoading(true)

    try {
      // Create complete waitlist entry with all survey data
      const result = await submitWaitlistEntry({
        email,
        budget,
        travel_team: travelTeam,
        recruiting_agency: recruitingAgency,
        graduation_year: graduationYear,
        recruiting_challenge: recruitingChallenge,
        desired_features: desiredFeatures,
        additional_info: additionalInfo,
      })

      console.log('[API] Survey data saved:', result)
      setSubmitted(true)
      
      // Clear sessionStorage
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
    // Redirect to success page
    window.location.href = "/waitlist/success"
    return null
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

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="bg-white rounded-3xl p-8 sm:p-12 shadow-xl border border-gray-100">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              Help us build something amazing!
            </h1>
            
            <p className="text-lg text-gray-600 leading-relaxed">
              We value your opinion, so please answer a few quick questions to help us create the perfect recruiting tool for you.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Budget Question */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                What&apos;s your budget for a recruiting tool like this? (One time payment) <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 gap-4">
                {[
                  "$99 or below",
                  "$99 to $199",
                  "$199 to $399", 
                  "Above $399"
                ].map((option) => (
                  <label key={option} className={`bg-gradient-to-r from-blue-50 to-red-50 border border-blue-100 rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-lg hover:scale-105 ${
                    budget === option ? 'ring-2 ring-blue-500 shadow-lg' : ''
                  }`}>
                    <input
                      type="radio"
                      name="budget"
                      value={option}
                      checked={budget === option}
                      onChange={(e) => setBudget(e.target.value)}
                      className="sr-only"
                    />
                    <div className="text-center">
                      <span className="text-lg font-semibold text-gray-800">{option}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Travel Team Question */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                Do you currently play for a summer baseball travel team? <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 gap-4">
                {[
                  "Yes",
                  "No"
                ].map((option) => (
                  <label key={option} className={`bg-gradient-to-r from-blue-50 to-red-50 border border-blue-100 rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-lg hover:scale-105 ${
                    travelTeam === option ? 'ring-2 ring-blue-500 shadow-lg' : ''
                  }`}>
                    <input
                      type="radio"
                      name="travelTeam"
                      value={option}
                      checked={travelTeam === option}
                      onChange={(e) => setTravelTeam(e.target.value)}
                      className="sr-only"
                    />
                    <div className="text-center">
                      <span className="text-lg font-semibold text-gray-800">{option}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Recruiting Agency Question */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                Do you already use a recruiting agency? <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 gap-4">
                {[
                  "Yes",
                  "No"
                ].map((option) => (
                  <label key={option} className={`bg-gradient-to-r from-blue-50 to-red-50 border border-blue-100 rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-lg hover:scale-105 ${
                    recruitingAgency === option ? 'ring-2 ring-blue-500 shadow-lg' : ''
                  }`}>
                    <input
                      type="radio"
                      name="recruitingAgency"
                      value={option}
                      checked={recruitingAgency === option}
                      onChange={(e) => setRecruitingAgency(e.target.value)}
                      className="sr-only"
                    />
                    <div className="text-center">
                      <span className="text-lg font-semibold text-gray-800">{option}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Graduation Year */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                What&apos;s the athlete&apos;s graduation year? <span className="text-red-500">*</span>
              </label>
              <select
                value={graduationYear}
                onChange={(e) => setGraduationYear(e.target.value)}
                className="w-full h-12 rounded-lg border border-gray-300 px-4 py-3 text-base text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="" className="text-gray-900">Select graduation year</option>
                {[2026, 2027, 2028, 2029].map((year) => (
                  <option key={year} value={year}>{year}</option>
                ))}
              </select>
            </div>

            {/* Recruiting Challenge Question */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                What&apos;s your biggest recruiting challenge or pain point?
              </label>
              <textarea
                value={recruitingChallenge}
                onChange={(e) => setRecruitingChallenge(e.target.value)}
                placeholder="e.g., finding the right schools, getting coach attention, understanding my chances, etc..."
                rows={3}
                className="w-full rounded-lg border border-gray-300 px-4 py-3 text-base text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              />
            </div>

            {/* Desired Features */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                What features would you love to see alongside the school matching algorithm?
              </label>
              <textarea
                value={desiredFeatures}
                onChange={(e) => setDesiredFeatures(e.target.value)}
                placeholder="e.g., email templates, coach contact info, team statistics, etc..."
                rows={3}
                className="w-full rounded-lg border border-gray-300 px-4 py-3 text-base text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              />
            </div>

            {/* Additional Info */}
            <div>
              <label className="block text-lg font-semibold text-gray-900 mb-4">
                Is there anything else you&apos;d like for the team to know?
              </label>
              <textarea
                value={additionalInfo}
                onChange={(e) => setAdditionalInfo(e.target.value)}
                placeholder="Any concerns, feedback, or other thoughts..."
                rows={3}
                className="w-full rounded-lg border border-gray-300 px-4 py-3 text-base text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              />
            </div>

            <Button 
              type="submit" 
              size="lg" 
              loading={loading}
              className="w-full text-lg py-4"
            >
              {loading ? "Joining..." : "Submit & Join Waitlist"}
            </Button>
          </form>
        </div>
      </main>
    </div>
  )
}