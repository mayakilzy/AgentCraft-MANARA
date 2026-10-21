import * as React from 'react';

/* ============================================================
   MANARA Lighthouse — brand mark and decorative illustration.

   The lighthouse is the central brand metaphor: a guiding light
   for research. The mark is a slim tower with a glowing lantern
   room and a soft beam. It must read as a lighthouse at 16px and
   at 320px.
   ============================================================ */

type LogoProps = React.SVGProps<SVGSVGElement> & {
  size?: number;
  variant?: 'ink' | 'teal' | 'canvas' | 'mist';
  withBeam?: boolean;
};

const palette: Record<NonNullable<LogoProps['variant']>, { tower: string; lantern: string; glow: string; beam: string }> = {
  ink: {
    tower: '#19334A',
    lantern: '#BB9362',
    glow: '#F2C879',
    beam: 'rgba(247, 200, 121, 0.65)',
  },
  teal: {
    tower: '#2C7380',
    lantern: '#BB9362',
    glow: '#F2C879',
    beam: 'rgba(247, 200, 121, 0.7)',
  },
  canvas: {
    tower: '#F7F8F6',
    lantern: '#BB9362',
    glow: '#F2C879',
    beam: 'rgba(247, 200, 121, 0.85)',
  },
  mist: {
    tower: '#E8EFF1',
    lantern: '#BB9362',
    glow: '#F2C879',
    beam: 'rgba(247, 200, 121, 0.7)',
  },
};

export function LighthouseLogo({
  size = 28,
  variant = 'ink',
  withBeam = true,
  className,
  ...rest
}: LogoProps) {
  const c = palette[variant];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="MANARA lighthouse mark"
      className={className}
      {...rest}
    >
      {/* Beam (subtle, soft) */}
      {withBeam && (
        <g className="manara-beam">
          <path
            d="M30.5 9.5 L46 4 L46 14 Z"
            fill={c.beam}
            opacity="0.65"
          />
          <path
            d="M31 11.5 L42 9 L42 13.5 Z"
            fill={c.glow}
            opacity="0.85"
          />
        </g>
      )}

      {/* Tower body — tapered, two-tone stripes */}
      <path
        d="M21 41 L27 41 L26.2 19 L21.8 19 Z"
        fill={c.tower}
      />
      {/* Stripes (brass) */}
      <path
        d="M21.6 36 L26.4 36 L26.3 33 L21.7 33 Z"
        fill={c.lantern}
        opacity="0.85"
      />
      <path
        d="M21.9 27 L26.1 27 L26 24 L22 24 Z"
        fill={c.lantern}
        opacity="0.85"
      />

      {/* Lantern room (top) */}
      <rect x="20.5" y="14" width="7" height="5" rx="0.6" fill={c.tower} />
      {/* Glowing light */}
      <circle cx="24" cy="16.5" r="1.6" fill={c.glow} />
      <circle cx="24" cy="16.5" r="2.6" fill={c.glow} opacity="0.35" />

      {/* Roof — pointed */}
      <path d="M19.5 14 L28.5 14 L24 9 Z" fill={c.tower} />
      {/* Finial */}
      <circle cx="24" cy="8.4" r="0.7" fill={c.lantern} />

      {/* Base / rocks */}
      <path
        d="M17 43 L31 43 L29.5 41 L18.5 41 Z"
        fill={c.tower}
        opacity="0.85"
      />
      <path
        d="M16 44 L32 44 L31 43 L17 43 Z"
        fill={c.tower}
        opacity="0.55"
      />
    </svg>
  );
}

/* ------------------------------------------------------------
   Decorative hero illustration — large lighthouse on a rocky
   cliff with a calm sea and stars. Editorial, calm.
   ------------------------------------------------------------ */

export function LighthouseHeroIllustration({
  className,
  ...rest
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 480 480"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Lighthouse illustration — guiding light on a rocky cliff"
      className={className}
      {...rest}
    >
      <defs>
        <linearGradient id="manara-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F7F8F6" />
          <stop offset="55%" stopColor="#E8EFF1" />
          <stop offset="100%" stopColor="#DCE7EA" />
        </linearGradient>
        <linearGradient id="manara-sea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#C7D8DC" />
          <stop offset="100%" stopColor="#9DB6BC" />
        </linearGradient>
        <linearGradient id="manara-cliff" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3B5872" />
          <stop offset="100%" stopColor="#19334A" />
        </linearGradient>
        <linearGradient id="manara-beam" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#F2C879" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#F2C879" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="manara-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#F4D69A" stopOpacity="1" />
          <stop offset="60%" stopColor="#F2C879" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#F2C879" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Sky */}
      <rect x="0" y="0" width="480" height="340" fill="url(#manara-sky)" />

      {/* Stars — small, sparse */}
      <g fill="#BB9362" opacity="0.55">
        <circle cx="60"  cy="50"  r="1.1" />
        <circle cx="120" cy="30"  r="0.9" />
        <circle cx="200" cy="70"  r="0.7" />
        <circle cx="90"  cy="100" r="0.8" />
        <circle cx="40"  cy="140" r="0.7" />
        <circle cx="170" cy="120" r="0.6" />
      </g>

      {/* Distant horizon line */}
      <line x1="0" y1="240" x2="480" y2="240" stroke="#9DB6BC" strokeWidth="0.6" opacity="0.5" />

      {/* Sea */}
      <rect x="0" y="300" width="480" height="120" fill="url(#manara-sea)" />
      {/* Water lines */}
      <g stroke="#7C99A1" strokeWidth="0.6" opacity="0.35">
        <path d="M0 318 Q 60 314 120 318 T 240 318 T 360 318 T 480 318" fill="none" />
        <path d="M0 338 Q 80 334 160 338 T 320 338 T 480 338" fill="none" />
        <path d="M0 362 Q 60 358 120 362 T 240 362 T 360 362 T 480 362" fill="none" />
        <path d="M0 388 Q 100 384 200 388 T 400 388 T 480 388" fill="none" />
      </g>

      {/* Cliff (right side) */}
      <path
        d="M260 480 L260 300 Q 280 285 300 290 L 360 295 Q 395 300 410 320 L 460 360 Q 478 378 480 400 L 480 480 Z"
        fill="url(#manara-cliff)"
      />
      {/* Cliff highlight */}
      <path
        d="M300 295 Q 320 305 340 330 L 360 360 Q 350 340 330 318 Q 314 302 300 295 Z"
        fill="#2C7380"
        opacity="0.18"
      />

      {/* Lighthouse beam — to the left (sea side) */}
      <g className="manara-beam">
        <path
          d="M282 150 L70 110 L70 200 Z"
          fill="url(#manara-beam)"
          opacity="0.55"
        />
        <path
          d="M282 158 L110 130 L110 180 Z"
          fill="url(#manara-beam)"
          opacity="0.45"
        />
      </g>

      {/* Lighthouse glow */}
      <circle cx="298" cy="160" r="55" fill="url(#manara-glow)" />

      {/* Lighthouse tower */}
      <g>
        {/* Base platform */}
        <rect x="280" y="220" width="36" height="8" fill="#19334A" />
        {/* Tower body — tapered */}
        <path d="M287 220 L309 220 L306 168 L290 168 Z" fill="#F7F8F6" />
        {/* Stripes */}
        <path d="M287.5 212 L308.5 212 L308 205 L288 205 Z" fill="#C44545" opacity="0.85" />
        <path d="M289 195 L307 195 L306.5 188 L289.5 188 Z" fill="#C44545" opacity="0.85" />
        <path d="M290 178 L306 178 L305.5 171 L290.5 171 Z" fill="#C44545" opacity="0.85" />

        {/* Lantern room */}
        <rect x="285" y="156" width="26" height="14" rx="1" fill="#19334A" />
        {/* Lantern windows */}
        <rect x="288" y="160" width="4" height="8" fill="#F4D69A" />
        <rect x="295" y="160" width="4" height="8" fill="#F4D69A" />
        <rect x="302" y="160" width="4" height="8" fill="#F4D69A" />
        {/* Central bright glow */}
        <circle cx="298" cy="164" r="6" fill="#F4D69A" />
        <circle cx="298" cy="164" r="9" fill="#F4D69A" opacity="0.45" />

        {/* Roof */}
        <path d="M283 156 L313 156 L298 142 Z" fill="#19334A" />
        {/* Finial */}
        <line x1="298" y1="142" x2="298" y2="134" stroke="#19334A" strokeWidth="1.5" />
        <circle cx="298" cy="133" r="2" fill="#BB9362" />

        {/* Railings */}
        <line x1="285" y1="170" x2="285" y2="156" stroke="#19334A" strokeWidth="1" />
        <line x1="311" y1="170" x2="311" y2="156" stroke="#19334A" strokeWidth="1" />
      </g>

      {/* Cliff foreground rocks */}
      <g fill="#19334A">
        <path d="M260 480 L260 330 Q 270 320 280 325 L 280 480 Z" opacity="0.95" />
      </g>
    </svg>
  );
}
