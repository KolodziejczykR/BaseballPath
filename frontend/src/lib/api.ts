// API utility functions for secure backend communication

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface WaitlistEntry {
  email: string
  user_type: string
  high_school_year: string
  email_consent: boolean
  raffle_entries?: number
}

export interface SurveyData {
  lead_id: string
  user_type?: string
  grad_year?: string
  college_level: string
  priorities: string[]
  priority_other?: string
  attended_showcases: string
  showcase_count?: string
  showcase_orgs?: string[]
  recruiting_budget: string
  tool_budget: number
  additional_features?: string
}

export interface ApiResponse<T> {
  data?: T
  error?: string
}

class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  }

  try {
    const response = await fetch(url, config)
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`
      throw new ApiError(errorMessage, response.status)
    }
    
    return await response.json()
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    
    console.error('[API] Request failed:', error)
    throw new ApiError('Network error. Please check your connection and try again.')
  }
}

export async function checkEmailExists(email: string): Promise<boolean> {
  try {
    const response = await apiRequest<{ exists: boolean }>('/waitlist/check-email', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
    
    return response.exists
  } catch (error) {
    console.error('[API] Error checking email:', error)
    throw error
  }
}

export async function submitWaitlistEntry(entry: WaitlistEntry): Promise<{ success: boolean; message: string; id?: string }> {
  try {
    const response = await apiRequest<{ success: boolean; message: string; id?: string }>('/waitlist/submit', {
      method: 'POST',
      body: JSON.stringify(entry),
    })
    
    return response
  } catch (error) {
    console.error('[API] Error submitting waitlist entry:', error)
    throw error
  }
}

export async function submitSurveyCompletion(surveyData: SurveyData): Promise<{ success: boolean; message: string; new_entries: number }> {
  try {
    const response = await apiRequest<{ success: boolean; message: string; new_entries: number }>('/waitlist/complete-survey', {
      method: 'POST',
      body: JSON.stringify(surveyData),
    })
    
    return response
  } catch (error) {
    console.error('[API] Error submitting survey completion:', error)
    throw error
  }
}

export async function getRaffleEntries(userId: string): Promise<{ raffle_entries: number; survey_completed: boolean }> {
  try {
    const response = await apiRequest<{ raffle_entries: number; survey_completed: boolean }>(`/waitlist/entries/${userId}`)
    
    return response
  } catch (error) {
    console.error('[API] Error getting raffle entries:', error)
    throw error
  }
}

export async function validateEmail(email: string): Promise<boolean> {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}