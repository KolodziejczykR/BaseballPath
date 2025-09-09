"use client"

import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { submitSurveyCompletion } from "@/lib/api"

// Force dynamic rendering to avoid build-time environment variable issues
export const dynamic = 'force-dynamic'

export default function PostSuccessLargeSurvey() {
  const [leadId, setLeadId] = useState("")
  const [userType, setUserType] = useState("")
  const [gradYear, setGradYear] = useState("")
  
  // Survey responses
  const [collegeLevel, setCollegeLevel] = useState("")
  const [priorities, setPriorities] = useState<string[]>([])
  const [priorityOther, setPriorityOther] = useState("")
  const [attendedShowcases, setAttendedShowcases] = useState("")
  const [showcaseCount, setShowcaseCount] = useState("")
  const [showcaseOrgs, setShowcaseOrgs] = useState<string[]>([])
  const [recruitingBudget, setRecruitingBudget] = useState("")
  const [toolBudget, setToolBudget] = useState("")
  const [additionalFeatures, setAdditionalFeatures] = useState("")
  
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  
  const searchParams = useSearchParams()

  // Handle priority checkbox changes (max 3)
  const handlePriorityChange = (priority: string, checked: boolean) => {
    if (checked) {
      if (priorities.length < 3) {
        setPriorities([...priorities, priority])
      }
    } else {
      setPriorities(priorities.filter(p => p !== priority))
      if (priority === 'other') {
        setPriorityOther('')
      }
    }
  }

  // Handle showcase org checkbox changes (multi-select)
  const handleShowcaseOrgChange = (org: string, checked: boolean) => {
    if (checked) {
      setShowcaseOrgs([...showcaseOrgs, org])
    } else {
      setShowcaseOrgs(showcaseOrgs.filter(o => o !== org))
    }
  }

  useEffect(() => {
    // Get URL parameters
    const leadIdParam = searchParams.get('lead_id') || ''
    const userTypeParam = searchParams.get('user_type') || ''
    const highSchoolYearParam = searchParams.get('high_school_year') || ''
    
    setLeadId(leadIdParam)
    setUserType(userTypeParam)
    setGradYear(highSchoolYearParam)
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (loading || submitted) {
      return
    }
    
    // Validate required fields
    if (!collegeLevel || priorities.length === 0 || !attendedShowcases || !recruitingBudget || !toolBudget) {
      alert("Please complete all required fields.")
      return
    }
    
    // Validate showcase sub-questions if attended
    if (attendedShowcases === "yes" && !showcaseCount) {
      alert("Please specify how many showcases you attended.")
      return
    }
    
    // Validate priorities count (max 3)
    if (priorities.length > 3) {
      alert("Please select up to 3 priorities only.")
      return
    }
    
    // Validate tool budget is numeric
    const toolBudgetNum = parseInt(toolBudget)
    if (isNaN(toolBudgetNum) || toolBudgetNum < 0) {
      alert("Please enter a valid dollar amount for tool budget.")
      return
    }
    
    setLoading(true)

    try {
      // Submit survey data and update raffle_entries to 4 (1 + 3 bonus)
      const surveyData = {
        lead_id: leadId,
        user_type: userType,
        grad_year: gradYear,
        college_level: collegeLevel,
        priorities: priorities,
        priority_other: priorityOther,
        attended_showcases: attendedShowcases,
        showcase_count: showcaseCount,
        showcase_orgs: showcaseOrgs,
        recruiting_budget: recruitingBudget,
        tool_budget: parseInt(toolBudget),
        additional_features: additionalFeatures
      }

      console.log('[Survey] Submitting data:', surveyData)
      
      // Call API to submit survey and update raffle entries
      const result = await submitSurveyCompletion(surveyData)
      
      console.log('[Survey] Success:', result)
      setSubmitted(true)
      
      // Redirect to thank you page with survey completion indicator
      setTimeout(() => {
        window.location.replace("/waitlist/survey-complete")
      }, 1000)
      
    } catch (err) {
      console.error("Survey submission error:", err)
      alert(err instanceof Error ? err.message : "There was an error submitting your survey. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="min-h-screen relative overflow-hidden font-sans flex items-center justify-center" style={{ backgroundColor: '#03032d', fontFamily: 'var(--font-manrope)' }}>
        <div className="text-center text-white">
          <div className="w-16 h-16 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-lg">Submitting your survey...</p>
        </div>
      </div>
    )
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

      <main className="relative z-10 max-w-4xl mx-auto px-6 lg:px-8 py-8">
        <div className="bg-white/5 backdrop-blur-sm rounded-3xl p-8 sm:p-12 border border-white/10">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-4">
              🎯 Bonus Survey: +3 Raffle Entries!
            </h1>
            
            <p className="text-lg text-white/70 leading-relaxed mb-2">
              Help us understand your recruiting journey so we can build the perfect solution for you.
            </p>
            
            <div className="inline-flex items-center px-4 py-2 rounded-full bg-emerald-900/40 border border-emerald-400/30">
              <span className="text-emerald-400 font-semibold">⚡ 2 minutes = Quadruple your entries</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Q1 - College Level */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                Which college baseball level feels realistic for you today? <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <select
                value={collegeLevel}
                onChange={(e) => setCollegeLevel(e.target.value)}
                className="w-full h-12 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm pl-4 pr-12 py-3 text-base text-white focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
              >
                <option value="" className="text-gray-900">Select level</option>
                <option value="power_4_d1" className="text-gray-900">Power 4 D1</option>
                <option value="non_p4_d1" className="text-gray-900">Non-P4 D1</option>
                <option value="division_2" className="text-gray-900">Division 2</option>
                <option value="division_3" className="text-gray-900">Division 3</option>
                <option value="not_sure" className="text-gray-900">Not sure yet</option>
              </select>
            </div>

            {/* Q2 - College Priorities */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                When choosing a college, what are your top priorities? <span className="text-sm text-white/60">(pick up to 3)</span> <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <div className="space-y-3">
                {[
                  'Tuition/Affordability',
                  'Academic Rating', 
                  'Athletic Rating',
                  'School Size',
                  'Location',
                  'Student Happiness',
                  'Party Scene',
                  'Other'
                ].map((priority) => (
                  <div key={priority} className="flex items-center">
                    <input
                      type="checkbox"
                      id={`priority-${priority}`}
                      checked={priorities.includes(priority)}
                      onChange={(e) => handlePriorityChange(priority, e.target.checked)}
                      disabled={!priorities.includes(priority) && priorities.length >= 3}
                      className="h-4 w-4 rounded border border-white/20 bg-white/10 text-emerald-600 focus:ring-emerald-400"
                    />
                    <label 
                      htmlFor={`priority-${priority}`} 
                      className={`ml-3 text-base text-white ${(!priorities.includes(priority) && priorities.length >= 3) ? 'opacity-50' : ''}`}
                    >
                      {priority}
                    </label>
                  </div>
                ))}
                {priorities.includes('Other') && (
                  <input
                    type="text"
                    value={priorityOther}
                    onChange={(e) => setPriorityOther(e.target.value)}
                    placeholder="Please specify..."
                    className="w-full h-10 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm pl-4 py-2 text-sm text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 ml-7 mt-2"
                  />
                )}
              </div>
              {priorities.length > 0 && (
                <p className="text-sm text-emerald-400 mt-2">
                  Selected: {priorities.length}/3
                </p>
              )}
            </div>

            {/* Q3 - Attended Showcases */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                Have you attended any showcases in the past 12 months? <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <div className="space-y-3">
                <div className="flex items-center">
                  <input
                    type="radio"
                    id="showcases-yes"
                    name="attended_showcases"
                    value="yes"
                    checked={attendedShowcases === "yes"}
                    onChange={(e) => setAttendedShowcases(e.target.value)}
                    className="h-4 w-4 text-emerald-600 focus:ring-emerald-400"
                  />
                  <label htmlFor="showcases-yes" className="ml-3 text-base text-white">Yes</label>
                </div>
                <div className="flex items-center">
                  <input
                    type="radio"
                    id="showcases-no"
                    name="attended_showcases"
                    value="no"
                    checked={attendedShowcases === "no"}
                    onChange={(e) => setAttendedShowcases(e.target.value)}
                    className="h-4 w-4 text-emerald-600 focus:ring-emerald-400"
                  />
                  <label htmlFor="showcases-no" className="ml-3 text-base text-white">No</label>
                </div>
              </div>
            </div>

            {/* Q3a & Q3b - Showcase Details (conditional) */}
            {attendedShowcases === "yes" && (
              <div className="space-y-6">
                {/* Q3a - How many showcases */}
                <div>
                  <label className="block text-lg font-semibold text-white mb-4">
                    About how many? <span style={{ color: '#6b7ff2' }}>*</span>
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {['1', '2', '3-4', '5+'].map((count) => (
                      <div key={count} className="flex items-center">
                        <input
                          type="radio"
                          id={`count-${count}`}
                          name="showcase_count"
                          value={count}
                          checked={showcaseCount === count}
                          onChange={(e) => setShowcaseCount(e.target.value)}
                          className="h-4 w-4 text-emerald-600 focus:ring-emerald-400"
                        />
                        <label htmlFor={`count-${count}`} className="ml-2 text-base text-white">{count}</label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Q3b - Showcase Organizations */}
                <div>
                  <label className="block text-lg font-semibold text-white mb-4">
                    Which organizations? <span className="text-sm text-white/60">(optional, multi-select)</span>
                  </label>
                  <div className="space-y-3">
                    {['PBR', 'Perfect Game', 'Headfirst', 'Showball', 'Prospect Select', 'Area Code', 'Other'].map((org) => (
                      <div key={org} className="flex items-center">
                        <input
                          type="checkbox"
                          id={`org-${org}`}
                          checked={showcaseOrgs.includes(org)}
                          onChange={(e) => handleShowcaseOrgChange(org, e.target.checked)}
                          className="h-4 w-4 rounded border border-white/20 bg-white/10 text-emerald-600 focus:ring-emerald-400"
                        />
                        <label htmlFor={`org-${org}`} className="ml-3 text-base text-white">{org}</label>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Q4 - Recruiting Budget */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                About how much do you plan to spend on your recruiting process? <span className="text-sm text-white/60">(includes showcases, camps, travel, etc.)</span> <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <select
                value={recruitingBudget}
                onChange={(e) => setRecruitingBudget(e.target.value)}
                className="w-full h-12 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm pl-4 pr-12 py-3 text-base text-white focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
              >
                <option value="" className="text-gray-900">Select budget range</option>
                <option value="under_500" className="text-gray-900">{'<$500'}</option>
                <option value="500_1500" className="text-gray-900">$500–$1,500</option>
                <option value="1500_3000" className="text-gray-900">$1,500–$3,000</option>
                <option value="3000_5000" className="text-gray-900">$3,000–$5,000</option>
                <option value="over_5000" className="text-gray-900">$5,000+</option>
              </select>
            </div>

            {/* Q5 - Tool Budget */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                How much would you be willing to spend on a recruiting tool like BaseballPath? <span style={{ color: '#6b7ff2' }}>*</span>
              </label>
              <input
                type="number"
                min="0"
                value={toolBudget}
                onChange={(e) => setToolBudget(e.target.value)}
                placeholder="Enter dollar amount (e.g., 250)"
                className="w-full h-12 rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm pl-4 pr-4 py-3 text-base text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
              />
            </div>

            {/* Q6 - Additional Features */}
            <div>
              <label className="block text-lg font-semibold text-white mb-4">
                Are there any features other than a list of compatible schools you would find useful? <span className="text-sm text-white/60">(optional)</span>
              </label>
              <textarea
                value={additionalFeatures}
                onChange={(e) => setAdditionalFeatures(e.target.value)}
                placeholder="Tell us about any additional features you'd find helpful..."
                rows={3}
                className="w-full rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm p-4 text-base text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 resize-none"
              />
            </div>

            <Button 
              type="submit" 
              size="lg" 
              loading={loading}
              className="w-full text-lg py-4 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg hover:shadow-xl active:shadow-md"
              style={{ 
                backgroundColor: '#10b981',
                borderColor: '#10b981',
                boxShadow: '0 4px 14px 0 rgba(16, 185, 129, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
              }}
            >
              {loading ? "Submitting Survey..." : "Complete Survey (+3 Entries) 🎯"}
            </Button>
          </form>
        </div>
      </main>
    </div>
  )
}