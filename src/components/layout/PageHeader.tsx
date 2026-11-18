import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  backHref?: string;
  backLabel?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  backHref,
  backLabel = 'Back',
  actions,
  children,
  className = '',
}: PageHeaderProps) {
  return (
    <div className={`pb-5 border-b border-[#e8e4d8] select-none ${className}`}>
      {backHref && (
        <div className="mb-2">
          <Link
            href={backHref}
            className="inline-flex items-center gap-1.5 text-xs text-[#6f7d3e] hover:text-[#4a5320] transition-colors no-underline font-medium"
          >
            <ArrowLeft size={13} />
            <span>{backLabel}</span>
          </Link>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          {eyebrow && (
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#6f7d3e] font-semibold mb-1">
              {eyebrow}
            </div>
          )}
          <h1 className="font-serif text-2xl sm:text-3xl text-[#1c1d1a] tracking-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="text-xs sm:text-sm text-[#5a5d52] mt-1 leading-relaxed max-w-2xl">
              {subtitle}
            </p>
          )}
        </div>

        {actions && (
          <div className="flex items-center gap-2.5 shrink-0 pt-1 sm:pt-0">
            {actions}
          </div>
        )}
      </div>

      {children && <div className="mt-3.5">{children}</div>}
    </div>
  );
}

