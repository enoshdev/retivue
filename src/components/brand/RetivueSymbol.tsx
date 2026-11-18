import React from 'react';

interface RetivueSymbolProps {
  className?: string;
  size?: number;
  variant?: 'light' | 'dark' | 'olive';
}

export function RetivueSymbol({
  className = '',
  size = 28,
  variant = 'olive',
}: RetivueSymbolProps) {
  // Theme color maps
  const strokeColor =
    variant === 'light'
      ? '#fbfbf9'
      : variant === 'dark'
      ? '#171913'
      : '#4a5320';

  const secondaryColor =
    variant === 'light'
      ? 'rgba(251, 251, 249, 0.45)'
      : variant === 'dark'
      ? 'rgba(23, 25, 19, 0.45)'
      : '#8a9178';

  const fovealFocalColor =
    variant === 'light'
      ? '#dee9a6'
      : variant === 'dark'
      ? '#4a5320'
      : '#333c0a';

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Retivue Symbol"
    >
      {/* Outer 45° Optical Retinal Aperture Ring */}
      <circle
        cx="20"
        cy="20"
        r="17"
        stroke={strokeColor}
        strokeWidth="1.75"
        strokeLinecap="round"
      />

      {/* Optical Reticle Cardinal Ticks */}
      <line x1="20" y1="1.5" x2="20" y2="4.5" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" />
      <line x1="20" y1="35.5" x2="20" y2="38.5" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" />
      <line x1="1.5" y1="20" x2="4.5" y2="20" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" />
      <line x1="35.5" y1="20" x2="38.5" y2="20" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" />

      {/* Primary Vascular / R-V Geometric Trajectory:
          Flows smoothly from left vertical stem, arcs upward into the R-chamber,
          and descends sharply through the focal center to form the V-vertex */}
      <path
        d="M 12 28 L 12 14.5 C 12 11.5 15.5 10 18.5 10 C 22.5 10 24.5 12.5 24.5 15.5 C 24.5 18 22.5 20 19 20 L 12 20"
        stroke={strokeColor}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Convergent V-Vector Path tracing toward central foveal focus */}
      <path
        d="M 18 20 L 23 28 L 28 17"
        stroke={strokeColor}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Concentric Macular Target Ring */}
      <circle
        cx="20"
        cy="20"
        r="6"
        stroke={secondaryColor}
        strokeWidth="1"
        strokeDasharray="2 2"
      />

      {/* Foveal Central Optical Pinpoint */}
      <circle
        cx="20"
        cy="20"
        r="1.75"
        fill={fovealFocalColor}
      />
    </svg>
  );
}
