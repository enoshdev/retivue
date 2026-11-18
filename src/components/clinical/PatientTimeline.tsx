'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  clinicalWorkflowApi,
  PatientTimelineResponse,
} from '@/lib/api';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import {
  Calendar,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Minus,
  Download,
  Loader2,
  GitCompare,
  ShieldCheck,
} from 'lucide-react';

interface PatientTimelineProps {
  patientId: string;
  onSelectForComparison?: (screeningId: string) => void;
  className?: string;
}

export function PatientTimeline({
  patientId,
  onSelectForComparison,
  className = '',
}: PatientTimelineProps) {
  const [timeline, setTimeline] = useState<PatientTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingPdfId, setDownloadingPdfId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    clinicalWorkflowApi
      .getPatientTimeline(patientId)
      .then((data) => {
        if (!active) return;
        setTimeline(data);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Unable to load patient timeline.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [patientId]);

  const handleDownloadPdf = async (screeningId: string) => {
    try {
      setDownloadingPdfId(screeningId);
      await clinicalWorkflowApi.downloadReportPdf(screeningId);
    } catch {
      // ignore
    } finally {
      setDownloadingPdfId(null);
    }
  };

  if (loading) {
    return (
      <div className={`p-8 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs text-center space-y-3 ${className}`}>
        <Loader2 size={20} className="animate-spin text-[#4a5320] mx-auto" />
        <p className="text-xs text-[#7a7d72] font-mono">Loading patient screening trajectory...</p>
      </div>
    );
  }

  if (error || !timeline || timeline.events.length === 0) {
    return (
      <div className={`p-6 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs text-center space-y-2 ${className}`}>
        <p className="text-xs text-[#7a7d72]">
          {error || 'No historical screening encounters recorded for this patient yet.'}
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Timeline Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#e8e4d8]">
        <div>
          <h3 className="font-serif text-base text-[#1c1d1a]">Longitudinal Screening Trajectory</h3>
          <p className="text-xs text-[#7a7d72] mt-0.5">{timeline.summary}</p>
        </div>
        <span className="inline-flex items-center px-3 py-1 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] text-xs font-mono font-semibold">
          {timeline.total_screenings} Encounter{timeline.total_screenings === 1 ? '' : 's'}
        </span>
      </div>

      {/* Trajectory Stream */}
      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-[#d8debe]">
        {timeline.events.map((event, index) => {
          const isBaseline = index === 0;
          const isLatest = index === timeline.events.length - 1;

          let trendIcon = <Minus size={13} className="text-[#7a7d72]" />;
          let trendBadge = (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#faf9f5] text-[#5a5d52] border border-[#e8e4d8]">
              {isBaseline ? 'Baseline Visit' : 'Stable Estimated Grade'}
            </span>
          );

          if (event.trend_category === 'higher_grade') {
            trendIcon = <TrendingUp size={13} className="text-amber-700" />;
            trendBadge = (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                Grade Shift (+; Review)
              </span>
            );
          } else if (event.trend_category === 'lower_grade') {
            trendIcon = <TrendingDown size={13} className="text-blue-700" />;
            trendBadge = (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-blue-50 text-blue-800 border border-blue-300">
                Grade Shift (-; Review)
              </span>
            );
          }

          return (
            <div key={event.screening_id} className="relative group">
              {/* Timeline Node Dot */}
              <div
                className={`absolute -left-6 top-1.5 w-5 h-5 rounded-full border-2 bg-white flex items-center justify-center transition-transform group-hover:scale-110 ${
                  isLatest
                    ? 'border-[#4a5320] text-[#4a5320]'
                    : isBaseline
                    ? 'border-[#6f7d3e] text-[#6f7d3e]'
                    : 'border-[#a8aba0] text-[#a8aba0]'
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    isLatest ? 'bg-[#4a5320]' : isBaseline ? 'bg-[#6f7d3e]' : 'bg-[#a8aba0]'
                  }`}
                />
              </div>

              {/* Event Card */}
              <div className="bg-white border border-[#e8e4d8] hover:border-[#b8c298] rounded-2xl p-5 shadow-xs transition-all space-y-3">
                {/* Event Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[#f0f2eb]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono font-bold text-xs text-[#1c1d1a]">
                      {event.screening_reference}
                    </span>
                    <span className="text-[#a8aba0] text-xs font-mono">•</span>
                    <span className="text-xs text-[#5a5d52] flex items-center gap-1">
                      <Calendar size={12} className="text-[#7a7d72]" />
                      {new Date(event.screening_date).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </span>
                    {isLatest && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#4a5320] text-white">
                        Latest
                      </span>
                    )}
                    {trendBadge}
                  </div>

                  <div className="flex items-center gap-2">
                    <StatusBadge type="status" value={event.status} size="sm" />
                  </div>
                </div>

                {/* Event Findings Row */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  {/* OD / OS AI Findings */}
                  <div className="p-3 bg-[#faf9f5] rounded-xl border border-[#e8e4d8] space-y-1">
                    <div className="text-[11px] font-mono font-semibold text-[#7a7d72] uppercase">
                      Bilateral DR Assessment
                    </div>
                    <div className="flex items-center justify-between pt-0.5">
                      <span className="text-[#5a5d52]">OD (Right):</span>
                      <span className="font-mono font-bold text-[#1c1d1a]">
                        {event.od_grade !== null && event.od_grade !== undefined
                          ? `Grade ${event.od_grade}`
                          : 'Pending'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#5a5d52]">OS (Left):</span>
                      <span className="font-mono font-bold text-[#1c1d1a]">
                        {event.os_grade !== null && event.os_grade !== undefined
                          ? `Grade ${event.os_grade}`
                          : 'Pending'}
                      </span>
                    </div>
                  </div>

                  {/* Risk & Review Status */}
                  <div className="p-3 bg-[#faf9f5] rounded-xl border border-[#e8e4d8] space-y-1">
                    <div className="text-[11px] font-mono font-semibold text-[#7a7d72] uppercase">
                      Referable Risk &amp; Sign-Off
                    </div>
                    <div className="flex items-center justify-between pt-0.5">
                      <span className="text-[#5a5d52]">Referable DR Risk:</span>
                      <span className="font-mono font-bold text-[#1c1d1a]">
                        {event.referable_dr_risk !== null && event.referable_dr_risk !== undefined
                          ? `${(event.referable_dr_risk * 100).toFixed(1)}%`
                          : '—'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#5a5d52]">Clinical Review:</span>
                      <span className="text-[#1c1d1a] font-medium truncate max-w-[120px]">
                        {event.reviewer_name || (event.status === 'reviewed' ? 'Completed' : 'Pending')}
                      </span>
                    </div>
                  </div>

                  {/* Actions & Links */}
                  <div className="p-3 bg-[#faf9f5] rounded-xl border border-[#e8e4d8] flex flex-col justify-between gap-2">
                    <div className="text-[11px] font-mono font-semibold text-[#7a7d72] uppercase">
                      Encounter Actions
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                      <Link
                        href={`/app/screenings/${event.screening_id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#4a5320] bg-white border border-[#d8debe] hover:bg-[#f2f4e8] rounded-full transition-colors no-underline"
                      >
                        <span>Workspace</span>
                        <ArrowRight size={11} />
                      </Link>

                      <button
                        type="button"
                        onClick={() => handleDownloadPdf(event.screening_id)}
                        disabled={downloadingPdfId === event.screening_id}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#5a5d52] bg-white border border-[#e8e4d8] hover:bg-[#f2f4e8] rounded-full transition-colors cursor-pointer disabled:opacity-50"
                        title="Download official PDF report"
                      >
                        {downloadingPdfId === event.screening_id ? (
                          <Loader2 size={11} className="animate-spin" />
                        ) : (
                          <Download size={11} />
                        )}
                        <span>PDF</span>
                      </button>

                      {onSelectForComparison && index > 0 && (
                        <button
                          type="button"
                          onClick={() => onSelectForComparison(event.screening_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#4a5320] bg-white border border-[#d8debe] hover:bg-[#f2f4e8] rounded-full transition-colors cursor-pointer"
                        >
                          <GitCompare size={11} />
                          <span>Compare</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Neutral Trend Observation */}
                <div className="text-[11px] text-[#7a7d72] flex items-center gap-1.5 pt-0.5">
                  {trendIcon}
                  <span>{event.trend_description}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Safety Notice Footer */}
      <div className="p-3 bg-[#f8f7f2] border border-[#e8e4d8] rounded-xl text-[11px] text-[#7a7d72] italic flex items-start gap-2">
        <ShieldCheck size={14} className="text-[#4a5320] shrink-0 mt-0.5" />
        <span>{timeline.clinical_safety_notice}</span>
      </div>
    </div>
  );
}
