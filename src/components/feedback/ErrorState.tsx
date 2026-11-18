import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Service Communication Error',
  message = 'An unexpected error occurred while communicating with the telemetry service. Please verify your connection or try again.',
  onRetry,
  className = '',
}: ErrorStateProps) {
  return (
    <div
      className={`p-8 text-center flex flex-col items-center justify-center bg-rose-50/50 border border-rose-200 rounded-lg ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-rose-100 flex items-center justify-center text-rose-600 mb-3">
        <AlertCircle size={22} />
      </div>
      <h3 className="text-sm font-semibold text-rose-900 mb-1">{title}</h3>
      <p className="text-xs text-rose-700 max-w-md mb-5 leading-relaxed">{message}</p>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 bg-rose-700 hover:bg-rose-800 text-white text-xs font-semibold px-4 py-2 rounded transition-colors"
        >
          <RefreshCw size={13} />
          <span>Retry Operation</span>
        </button>
      )}
    </div>
  );
}

