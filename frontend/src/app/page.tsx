"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to waitlist page immediately
    router.push("/waitlist")
  }, [router])

  return (
    <div className="min-h-screen relative overflow-hidden font-sans flex items-center justify-center" style={{ backgroundColor: '#03032d', fontFamily: 'var(--font-manrope)' }}>
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
      <header className="absolute top-0 left-0 right-0 z-10 w-full">
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
      <div className="relative z-10 text-center max-w-4xl mx-auto px-6">
        <div className="mb-8">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-6 mx-auto" 
               style={{ 
                 backgroundColor: '#6b7ff2',
                 boxShadow: '0 4px 20px rgba(107, 127, 242, 0.4)'
               }}>
            <svg className="w-8 h-8 text-white animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          
          <h1 className="text-5xl sm:text-6xl font-bold text-white mb-4 leading-tight">
            The AI That{" "}
            <span style={{ 
              background: 'linear-gradient(135deg, #6b7ff2 0%, #10b981 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
              Gets You Recruited
            </span>
          </h1>
          
          <p className="text-xl text-white/70 mb-2">
            Loading BaseballPATH waitlist...
          </p>
          
          <div className="flex justify-center items-center space-x-2">
            <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse"></div>
            <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
            <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
          </div>
        </div>
      </div>
    </div>
  )
}
