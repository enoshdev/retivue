import React from 'react';
import { DRGrade, ScreeningCaseStatus, CaseUrgency, ImageSuitability } from '@/types/clinical';

interface StatusBadgeProps {
  type?: 'grade' | 'status' | 'urgency' | 'quality';
  value: DRGrade | ScreeningCaseStatus | CaseUrgency | ImageSuitability | string;
  size?: 'sm' | 'md';
  className?: string;
}

export function StatusBadge({
  type = 'status',
  value,
  size = 'md',
  className = '',
}: StatusBadgeProps) {
  const sizeClasses =
    size === 'sm'
      ? 'text-[11px] px-2.5 py-0.5'
      : 'text-xs px-3 py-1';

  // DR Grade styling
  if (type === 'grade' || value === 'NO_DR' || value === 'MILD_NPDR' || value === 'MODERATE_NPDR' || value === 'SEVERE_NPDR' || value === 'PDR') {
    switch (value) {
      case 'NO_DR':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-emerald-50/80 text-emerald-800 border-emerald-200/80 ${sizeClasses} ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            No Apparent DR
          </span>
        );
      case 'MILD_NPDR':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-amber-50/80 text-amber-800 border-amber-200/80 ${sizeClasses} ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
            Mild NPDR
          </span>
        );
      case 'MODERATE_NPDR':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-semibold rounded-full border bg-amber-50/90 text-amber-900 border-amber-300/80 ${sizeClasses} ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-600 shrink-0" />
            Moderate NPDR
          </span>
        );
      case 'SEVERE_NPDR':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-semibold rounded-full border bg-rose-50/90 text-rose-800 border-rose-200/80 ${sizeClasses} ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600 shrink-0" />
            Severe NPDR
          </span>
        );
      case 'PDR':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-bold rounded-full border bg-rose-100/90 text-rose-900 border-rose-300 ${sizeClasses} ${className}`}
          >
            <span className="w-2 h-2 rounded-full bg-rose-700 animate-pulse shrink-0" />
            Proliferative DR (Urgent)
          </span>
        );
      default:
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-slate-100 text-slate-700 border-slate-200/80 ${sizeClasses} ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0" />
            Pending Analysis
          </span>
        );
    }
  }

  // Case Status styling (Phase 4 Real Lifecycle + Compatibility)
  if (value === 'ready_for_quality_assessment') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-semibold rounded-full border bg-[#f2f4e8] text-[#4a5320] border-[#d8debe] ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-[#4a5320] shrink-0" />
        Ready for Quality Assessment
      </span>
    );
  }
  if (value === 'ready_for_quality_assessment') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-sky-50/80 text-sky-800 border-sky-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-sky-600 shrink-0" />
        Ready for Quality Check
      </span>
    );
  }
  if (value === 'quality_failed_recapture_required') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-amber-100/90 text-amber-900 border-amber-300 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-700 shrink-0" />
        Quality Failed (Recapture Required)
      </span>
    );
  }
  if (value === 'ai_completed_review_required') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-amber-50/90 text-amber-900 border-amber-300 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-600 shrink-0" />
        AI Completed (Review Required)
      </span>
    );
  }
  if (value === 'ai_completed_advisory') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-emerald-50/80 text-emerald-800 border-emerald-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0" />
        AI Advisory Ready
      </span>
    );
  }
  if (value === 'ai_failed_review_required') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-rose-50/90 text-rose-800 border-rose-200 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-rose-600 shrink-0" />
        AI Error (Review Required)
      </span>
    );
  }
  if (value === 'clinically_reviewed_signed' || value === 'REVIEWED') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-semibold rounded-full border bg-emerald-50/90 text-emerald-900 border-emerald-300 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0" />
        Clinically Signed Off
      </span>
    );
  }
  if (value === 'draft') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-emerald-50/80 text-emerald-800 border-emerald-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0" />
        Draft (Bilateral Captured)
      </span>
    );
  }
  if (value === 'images_incomplete') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-amber-50/80 text-amber-800 border-amber-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
        Images Incomplete
      </span>
    );
  }
  if (value === 'awaiting_images') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-slate-100 text-slate-700 border-slate-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0" />
        Awaiting Images
      </span>
    );
  }
  if (value === 'cancelled' || value === 'archived') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-slate-100 text-slate-500 border-slate-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0" />
        {value === 'cancelled' ? 'Cancelled' : 'Archived'}
      </span>
    );
  }
  if (value === 'AWAITING_REVIEW') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-amber-50/80 text-amber-800 border-amber-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
        Awaiting Review
      </span>
    );
  }
  if (value === 'REVIEWED') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-emerald-50/80 text-emerald-800 border-emerald-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0" />
        Reviewed & Signed
      </span>
    );
  }
  if (value === 'REFERRED') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-semibold rounded-full border bg-rose-50/80 text-rose-800 border-rose-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-rose-600 shrink-0" />
        Referred to Specialist
      </span>
    );
  }
  if (value === 'QUALITY_CHECK' || value === 'RECAPTURE_REQUIRED' || value === 'UNGRADEABLE') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-amber-100/80 text-amber-900 border-amber-300/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-700 shrink-0" />
        {value === 'UNGRADEABLE' ? 'Ungradeable (Recapture)' : 'Quality Audit Required'}
      </span>
    );
  }
  if (value === 'SUITABLE' || value === 'OPTIMAL') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-emerald-50/80 text-emerald-700 border-emerald-200/80 ${sizeClasses} ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
        Gradable / Optimal
      </span>
    );
  }

  // Fallback
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border bg-slate-50 text-slate-700 border-slate-200/80 ${sizeClasses} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0" />
      {String(value).replace(/_/g, ' ')}
    </span>
  );
}

