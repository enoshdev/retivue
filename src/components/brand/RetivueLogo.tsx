import React from 'react';
import Link from 'next/link';
import { RetivueSymbol } from './RetivueSymbol';
import { RetivueWordmark } from './RetivueWordmark';

interface RetivueLogoProps {
  className?: string;
  variant?: 'light' | 'dark' | 'olive';
  size?: 'sm' | 'md' | 'lg';
  type?: 'primary' | 'compact' | 'wordmark';
  href?: string;
}

export function RetivueLogo({
  className = '',
  variant = 'olive',
  size = 'md',
  type = 'primary',
  href = '/',
}: RetivueLogoProps) {
  const symbolSizes = {
    sm: 22,
    md: 28,
    lg: 36,
  };

  const wordmarkSizes: Record<'sm' | 'md' | 'lg', 'sm' | 'md' | 'lg'> = {
    sm: 'sm',
    md: 'md',
    lg: 'lg',
  };

  const content = (
    <div className={`inline-flex items-center gap-2.5 group cursor-pointer ${className}`}>
      {type !== 'wordmark' && (
        <RetivueSymbol
          size={symbolSizes[size]}
          variant={variant}
          className="transition-transform duration-300 group-hover:scale-105"
        />
      )}
      {type !== 'compact' && (
        <div className="flex items-center">
          <RetivueWordmark
            size={wordmarkSizes[size]}
            variant={variant}
          />
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex items-center no-underline">
        {content}
      </Link>
    );
  }

  return content;
}
