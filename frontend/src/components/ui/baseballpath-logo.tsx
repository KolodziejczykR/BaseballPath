interface BaseballPathLogoProps {
  width?: number
  height?: number
  className?: string
}

{/* 
  TODO: 
  - fix the logo...
*/}

export function BaseballPathLogo({ 
  width = 40, 
  height = 40, 
  className = "" 
}: BaseballPathLogoProps) {
  return (
    <svg 
      width={width} 
      height={height} 
      viewBox="0 0 120 120" 
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Blue to red gradient for the background */}
        <linearGradient id="backgroundGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#dc2626" />
        </linearGradient>
        
        {/* Baseball gradient - classic white with red stitching */}
        <radialGradient id="baseballGradient" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="80%" stopColor="#f8fafc" />
          <stop offset="100%" stopColor="#e2e8f0" />
        </radialGradient>
      </defs>
      
      {/* Rounded square background */}
      <rect
        x="10"
        y="10"
        width="100"
        height="100"
        rx="20"
        ry="20"
        fill="url(#backgroundGradient)"
        stroke="none"
      />
      
      {/* Large BP letters like in sketch */}
      {/* Letter B - occupying upper portion */}
      <path
        d="M20 20 L20 70 L55 70 C67 70 75 62 75 50 C75 43 72 37 67 35 C72 33 75 27 75 20 C75 8 67 0 55 0 L20 0 L20 20 Z M35 15 L55 15 C60 15 63 18 63 23 C63 28 60 31 55 31 L35 31 Z M35 46 L55 46 C60 46 63 49 63 54 C63 59 60 62 55 62 L35 62 Z"
        fill="white"
        stroke="none"
        transform="translate(15, 25) scale(0.85)"
      />
      
      {/* Letter P - occupying lower portion, overlapping with B */}
      <path
        d="M0 20 L0 90 L15 90 L15 60 L45 60 C57 60 65 52 65 40 L65 20 C65 8 57 0 45 0 L0 0 L0 20 Z M15 15 L45 15 C52 15 55 18 55 23 L55 37 C55 42 52 45 45 45 L15 45 Z"
        fill="white"
        stroke="none"
        transform="translate(45, 45) scale(0.85)"
      />
    </svg>
  )
}