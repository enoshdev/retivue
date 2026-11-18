import React from 'react';

interface RetivueWordmarkProps {
  className?: string;
  variant?: 'light' | 'dark' | 'olive';
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export function RetivueWordmark({
  className = '',
  variant = 'dark',
  size = 'md',
}: RetivueWordmarkProps) {
  const textColor =
    variant === 'light'
      ? 'text-[#fbfbf9]'
      : variant === 'olive'
      ? 'text-[#4a5320]'
      : 'text-[#171913]';

  const sizeClasses = {
    sm: 'text-xs tracking-[0.24em]',
    md: 'text-sm tracking-[0.22em]',
    lg: 'text-lg tracking-[0.2em]',
    xl: 'text-2xl tracking-[0.18em]',
  };

  return (
    <span
      className={`font-semibold font-sans uppercase select-none transition-colors ${textColor} ${sizeClasses[size]} ${className}`}
      style={{ letterSpacing: '0.22em' }}
    >
      RETIVUE
    </span>
  );
}
