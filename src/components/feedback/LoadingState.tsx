import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  subtext?: string;
  className?: string;
}

export function LoadingState({
  message = 'Loading clinical data...',
  subtext = 'Validating records against active telemetry database',
  className = '',
}: LoadingStateProps) {
  return (
    <div
      className={`p-12 text-center flex flex-col items-center justify-center bg-white border border-slate-200 rounded-lg ${className}`}
    >
      <Loader2 size={24} className="animate-spin text-slate-700 mb-3" />
      <h3 className="text-sm font-semibold text-slate-900 mb-1">{message}</h3>
      <p className="text-xs text-slate-500 font-mono">{subtext}</p>
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4 bg-white border border-slate-200 rounded-lg animate-pulse">
      <div className="h-4 bg-slate-100 rounded w-1/4 mb-4" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-8 bg-slate-50 rounded w-full" />
      ))}
    </div>
  );
}

