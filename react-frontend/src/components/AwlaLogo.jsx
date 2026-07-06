import { useId } from 'react'

export default function AwlaLogo({ size = 32, showText = true }) {
  const raw = useId()
  const uid = raw.replace(/[^a-zA-Z0-9]/g, '')

  const gMain = `gm${uid}`
  const gDark = `gd${uid}`
  const gText = `gt${uid}`

  const w = size
  const h = showText ? Math.round(size * 1.15) : size
  const vb = showText ? '0 0 200 230' : '0 0 200 200'

  return (
    <svg
      width={w}
      height={h}
      viewBox={vb}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Diagonal teal→blue gradient for main ribbon surfaces */}
        <linearGradient id={gMain} x1="0" y1="0" x2="200" y2="200" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#1ECFB3" />
          <stop offset="100%" stopColor="#1155CC" />
        </linearGradient>
        {/* Darker variant for shadow/depth areas */}
        <linearGradient id={gDark} x1="0" y1="0" x2="200" y2="200" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#0DA898" />
          <stop offset="100%" stopColor="#0A3C8F" />
        </linearGradient>
        {/* Horizontal gradient for the 'awla' text */}
        <linearGradient id={gText} x1="0" y1="0" x2="200" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#1ECFB3" />
          <stop offset="100%" stopColor="#1155CC" />
        </linearGradient>
      </defs>

      {/* ── Floating pixel dots (cascade from upper-left) ── */}
      <rect x="7"  y="22" width="6" height="6" rx="0.5" fill={`url(#${gMain})`} opacity="0.95" />
      <rect x="17" y="14" width="5" height="5" rx="0.5" fill={`url(#${gMain})`} opacity="0.82" />
      <rect x="27" y="7"  width="4" height="4" rx="0.5" fill={`url(#${gMain})`} opacity="0.68" />
      <rect x="36" y="2"  width="3" height="3" rx="0.5" fill={`url(#${gMain})`} opacity="0.5"  />
      <rect x="3"  y="32" width="5" height="5" rx="0.5" fill={`url(#${gMain})`} opacity="0.72" />
      <rect x="13" y="26" width="4" height="4" rx="0.5" fill={`url(#${gMain})`} opacity="0.58" />
      <rect x="22" y="20" width="3" height="3" rx="0.5" fill={`url(#${gMain})`} opacity="0.44" />
      <rect x="1"  y="42" width="4" height="4" rx="0.5" fill={`url(#${gMain})`} opacity="0.52" />
      <rect x="9"  y="36" width="3" height="3" rx="0.5" fill={`url(#${gMain})`} opacity="0.38" />

      {/* ── Main A-shape ribbon (drawn back→front) ── */}

      {/* Layer 1 — right bottom cap (goes under / behind) */}
      <path
        d="M 188,163 L 170,154 C 178,147 190,149 193,160 C 196,170 193,175 188,163 Z"
        fill={`url(#${gDark})`}
        opacity="0.88"
      />

      {/* Layer 2 — bottom bar: the back part of the Möbius crossing */}
      <path
        d="M 42,157 C 62,148 80,144 100,144 C 120,144 138,148 158,157
           C 138,169 120,173 100,173 C 80,173 62,169 42,157 Z"
        fill={`url(#${gDark})`}
      />

      {/* Layer 3 — right leg of the A */}
      <path
        d="M 103,18 L 100,45 L 158,157 L 188,163 Z"
        fill={`url(#${gMain})`}
      />

      {/* Layer 4 — left leg of the A (in front of right leg) */}
      <path
        d="M 97,18 L 12,163 L 42,157 L 100,45 Z"
        fill={`url(#${gMain})`}
      />

      {/* Layer 5 — left bottom cap (front face, goes over the crossing) */}
      <path
        d="M 12,163 C 5,172 4,167 7,159 C 10,149 20,148 29,153
           L 42,157 C 30,164 14,169 12,163 Z"
        fill={`url(#${gMain})`}
      />

      {/* Layer 6 — front crossing highlight (ribbon going OVER the bottom bar) */}
      <path
        d="M 68,144 C 79,139 89,136 100,136 C 111,136 121,139 132,144
           L 130,152 C 119,147 110,144 100,144 C 90,144 81,147 70,152 Z"
        fill={`url(#${gMain})`}
        opacity="0.78"
      />

      {/* ── </> code symbol inside the triangle hollow ── */}
      <text
        x="100"
        y="112"
        textAnchor="middle"
        dominantBaseline="middle"
        fill={`url(#${gMain})`}
        fontSize="22"
        fontFamily="'SF Mono', 'Consolas', 'Courier New', monospace"
        fontWeight="700"
        opacity="0.85"
      >
        &lt;/&gt;
      </text>

      {/* ── 'awla' wordmark with decorative accent lines (only when showText=true) ── */}
      {showText && (
        <>
          <line
            x1="16" y1="209" x2="58" y2="209"
            stroke={`url(#${gText})`} strokeWidth="1.5" strokeLinecap="round" opacity="0.6"
          />
          <text
            x="100"
            y="211"
            textAnchor="middle"
            dominantBaseline="middle"
            fill={`url(#${gText})`}
            fontSize="40"
            fontFamily="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
            fontWeight="800"
            letterSpacing="-1"
          >
            awla
          </text>
          <line
            x1="142" y1="209" x2="184" y2="209"
            stroke={`url(#${gText})`} strokeWidth="1.5" strokeLinecap="round" opacity="0.6"
          />
        </>
      )}
    </svg>
  )
}
