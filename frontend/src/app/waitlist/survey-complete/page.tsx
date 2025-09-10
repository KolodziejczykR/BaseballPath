"use client"

import { useEffect } from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';

export default function SurveyCompletePage() {
  useEffect(() => {
    // Clear session storage to prevent going back to surveys
    sessionStorage.removeItem("waitlist_user_id");
    sessionStorage.removeItem("waitlist_user_type"); 
    sessionStorage.removeItem("waitlist_high_school_year");
    
    // Simple approach: just handle the back button event
    const handlePopState = () => {
      // Prevent default back behavior and redirect to waitlist
      window.location.href = '/waitlist';
    };
    
    // Add a state to the history so we can catch the popstate
    window.history.pushState(null, document.title, window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);
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
              Survey Complete!
            </h1>
            
            <p className="text-lg text-white/70 mb-8 leading-relaxed">
              Awesome! You now have <span className="text-emerald-400 font-bold">4 raffle entries</span> for our launch giveaway. Your insights will help us build the perfect recruiting solution!
            </p>

            <div className="bg-gradient-to-r from-emerald-900/40 to-teal-900/40 rounded-xl p-6 border border-emerald-400/20 backdrop-blur-sm mb-8">
              <div className="flex items-center justify-center mb-4">
                <div className="text-4xl font-bold text-emerald-400">4</div>
                <div className="ml-2 text-white/80">
                  <div className="text-sm">Total Raffle</div>
                  <div className="text-sm font-semibold">Entries</div>
                </div>
              </div>
              <p className="text-emerald-300 text-sm font-medium">
                ✨ 4x better odds to win BaseballPATH free on launch day!
              </p>
            </div>

            <div className="bg-gradient-to-r from-purple-900/40 to-blue-900/40 rounded-xl p-6 border border-white/10 backdrop-blur-sm">
              <p className="text-white/80 font-medium mb-4">
                What&apos;s next?
              </p>
              <ul className="text-white/70 text-sm space-y-2 text-left">
                <li>• We&apos;ll analyze your responses to tailor our platform</li>
                <li>• Look out for exclusive updates in your inbox</li>
                <li>• Raffle drawing happens at launch day</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}