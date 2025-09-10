"use client"

import { DotLottieReact } from '@lottiefiles/dotlottie-react';

export default function SuccessPage() {
  return (
    <div className="min-h-screen relative overflow-hidden font-sans" style={{ backgroundColor: '#03032d', fontFamily: 'var(--font-manrope)' }}>
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
            top: 10%;
          }
          24%, 34% {
            opacity: 0.1;
            left: -15%;
            top: 10%;
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
      <main className="relative z-10 flex items-center justify-center px-6 lg:px-8" style={{ minHeight: 'calc(100vh - 120px)' }}>
        <div className="max-w-2xl mx-auto text-center">
          <div className="bg-white/5 backdrop-blur-sm rounded-3xl p-12 border border-white/10">
            <div className="w-[120px] h-[120px] flex items-center justify-center mb-8 mx-auto">
              <DotLottieReact
                src="https://lottie.host/30ae7aa1-e851-4a93-90d5-097472ea52bb/zxCF5pASeC.lottie"
                loop={false}
                autoplay
                style={{ width: '120px', height: '120px' }}
              />
            </div>
            
            <h1 className="text-4xl font-bold text-white mb-6">
              Perfect! You&apos;re all set!
            </h1>
            
            <p className="text-xl text-white/70 mb-8 leading-relaxed">
              Thanks for joining the BaseballPath waitlist and sharing your feedback. We&apos;ll be in touch soon with more details!
            </p>

            {/* Bonus Survey CTA */}
            <div className="bg-gradient-to-r from-emerald-900/40 to-teal-900/40 rounded-xl p-8 border border-white/10 backdrop-blur-sm">
              <h3 className="text-2xl font-bold text-white mb-4">
                🎯 Want 3 bonus entries?
              </h3>
              <p className="text-white/80 mb-6 leading-relaxed">
                Take our 2-minute survey to help us tailor your perfect match. Complete it now and we&apos;ll 4x your raffle entries!
              </p>
              <button
                onClick={() => {
                  // Get the user data from sessionStorage
                  const userId = sessionStorage.getItem("waitlist_user_id") || ""
                  const userType = sessionStorage.getItem("waitlist_user_type") || ""
                  const highSchoolYear = sessionStorage.getItem("waitlist_high_school_year") || ""
                  
                  if (!userId) {
                    alert("Session expired. Please start over from the waitlist page.")
                    window.location.href = "/waitlist"
                    return
                  }
                  
                  // Navigate with actual user data as URL parameters
                  window.location.href = `/waitlist/post_success_large_survey?lead_id=${userId}&user_type=${userType}&high_school_year=${highSchoolYear}`
                }}
                className="w-full py-4 px-6 rounded-lg font-semibold text-lg transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg hover:shadow-xl mb-4"
                style={{ 
                  backgroundColor: '#10b981',
                  color: 'white',
                  boxShadow: '0 4px 14px 0 rgba(16, 185, 129, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
                }}
              >
                Start 2-Minute Survey (+3 entries) →
              </button>
              
              <button
                onClick={() => {
                  // Clear session data and return to waitlist
                  sessionStorage.removeItem("waitlist_user_id")
                  sessionStorage.removeItem("waitlist_user_type")
                  sessionStorage.removeItem("waitlist_high_school_year")
                  window.location.href = "/waitlist"
                }}
                className="w-full py-3 px-6 rounded-lg text-sm font-medium transition-all duration-200 hover:bg-white/10"
                style={{ 
                  backgroundColor: 'transparent',
                  color: '#white',
                  border: '1px solid rgba(255, 255, 255, 0.2)'
                }}
              >
                I&apos;m all set
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}