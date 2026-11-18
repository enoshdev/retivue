'use client';

import React, { useEffect, useState } from 'react';
import {
  clinicalWorkflowApi,
  screeningApi,
  ScreeningComparisonResponse,
  EyeComparisonResult,
  ApiScreening,
} from '@/lib/api';
import {
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Info,
  Loader2,
  Sliders,
} from 'lucide-react';

interface ScreeningComparisonViewerProps {
  currentScreeningId: string;
  patientId: string;
  initialPreviousScreeningId?: string;
  className?: string;
}

const DR_GRADE_LABELS: Record<number, string> = {
  0: 'No DR',
  1: 'Mild NPDR',
  2: 'Moderate NPDR',
  3: 'Severe NPDR',
  4: 'Proliferative DR',
};

function ComparisonFundusImage({
  screeningId,
  eye,
  mode,
  targetClass,
  alt,
}: {
  screeningId: string;
  eye: 'OD' | 'OS';
  mode: 'original' | 'overlay';
  targetClass?: number;
  alt: string;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let url: string | null = null;

    const fetcher =
      mode === 'original'
        ? screeningApi.fetchImageBlobUrl(screeningId, eye)
        : clinicalWorkflowApi.fetchExplanationImageBlobUrl(screeningId, eye, 'overlay', targetClass);

    fetcher
      .then((u) => {
        if (!active) {
          URL.revokeObjectURL(u);
          return;
        }
        url = u;
        setBlobUrl(u);
        setError(null);
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Image unavailable.');
          setBlobUrl(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [screeningId, eye, mode, targetClass]);

  if (loading) {
    return (
      <div className="w-full h-56 bg-[#151613] rounded-xl border border-[#2b2e24] flex flex-col items-center justify-center text-[#8e9185] text-xs font-mono gap-2">
        <Loader2 size={18} className="animate-spin text-[#dee9a6]" />
        <span>Loading {mode === 'original' ? 'Scan' : 'Grad-CAM Overlay'}...</span>
      </div>
    );
  }

  if (error || !blobUrl) {
    return (
      <div className="w-full h-56 bg-[#151613] rounded-xl border border-[#2b2e24] flex flex-col items-center justify-center text-[#8e9185] text-xs font-mono p-4 text-center gap-1.5">
        <AlertTriangle size={18} className="text-amber-400" />
        <span className="text-[#edebe1] font-medium">Image Not Available</span>
        <span className="text-[11px] text-[#7a7d72] max-w-xs">{error || 'No scan or overlay recorded for this visit.'}</span>
      </div>
    );
  }

  return (
    <div className="relative w-full h-56 bg-black rounded-xl overflow-hidden border border-[#2b2e24] flex items-center justify-center">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={blobUrl} alt={alt} className="w-full h-full object-contain pointer-events-none" />
    </div>
  );
}

function EyeComparisonCard({
  eye,
  comparison,
  currentScreeningId,
  previousScreeningId,
  currentDate,
  previousDate,
}: {
  eye: 'OD' | 'OS';
  comparison: EyeComparisonResult;
  currentScreeningId: string;
  previousScreeningId: string;
  currentDate: string;
  previousDate: string;
}) {
  const [viewMode, setViewMode] = useState<'original' | 'overlay'>('overlay');

  const eyeTitle = eye === 'OD' ? 'Right Eye (OD)' : 'Left Eye (OS)';
  const prevGrade = comparison.previous_grade;
  const currGrade = comparison.current_grade;
  const prevLabel = prevGrade !== null && prevGrade !== undefined ? DR_GRADE_LABELS[prevGrade] || `Grade ${prevGrade}` : 'Unassessed';
  const currLabel = currGrade !== null && currGrade !== undefined ? DR_GRADE_LABELS[currGrade] || `Grade ${currGrade}` : 'Unassessed';
  const delta = comparison.grade_difference;

  let deltaBadge = (
    <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-[#f0f2eb] text-[#5a5d52] border border-[#d8debe]">
      Grade Delta: 0 (Stable)
    </span>
  );
  if (delta !== null && delta !== undefined) {
    if (delta > 0) {
      deltaBadge = (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-amber-50 text-amber-800 border border-amber-300">
          Grade Delta: +{delta} (Shifted Higher)
        </span>
      );
    } else if (delta < 0) {
      deltaBadge = (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-blue-50 text-blue-800 border border-blue-300">
          Grade Delta: {delta} (Shifted Lower)
        </span>
      );
    }
  }

  return (
    <div className="bg-[#faf9f5] border border-[#e8e4d8] rounded-2xl p-5 space-y-4">
      {/* Eye Card Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#e8e4d8]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-[#4a5320] text-white flex items-center justify-center font-mono font-bold text-xs">
            {eye}
          </div>
          <div>
            <h4 className="font-serif text-base text-[#1c1d1a]">{eyeTitle}</h4>
            <p className="text-[11px] text-[#7a7d72] font-mono">
              Bilateral Match: {comparison.has_previous_image && comparison.has_current_image ? 'Both Scans Available' : 'Partial Scan Available'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {deltaBadge}
          {/* Mode Switcher */}
          <div className="inline-flex rounded-full bg-white p-0.5 border border-[#d8debe]">
            <button
              type="button"
              onClick={() => setViewMode('overlay')}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                viewMode === 'overlay' ? 'bg-[#4a5320] text-white shadow-2xs' : 'text-[#5a5d52] hover:text-[#1c1d1a]'
              }`}
            >
              Grad-CAM
            </button>
            <button
              type="button"
              onClick={() => setViewMode('original')}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                viewMode === 'original' ? 'bg-[#4a5320] text-white shadow-2xs' : 'text-[#5a5d52] hover:text-[#1c1d1a]'
              }`}
            >
              Original Scan
            </button>
          </div>
        </div>
      </div>

      {/* Side-by-Side Fundus Imagery */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Previous Image */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-[#5a5d52] flex items-center gap-1.5">
              <Clock size={13} className="text-[#7a7d72]" />
              Prior Encounter ({new Date(previousDate).toLocaleDateString()})
            </span>
            <span className="font-mono text-[11px] font-bold text-[#1c1d1a]">
              {prevGrade !== null && prevGrade !== undefined ? `Grade ${prevGrade} (${prevLabel})` : 'No Result'}
            </span>
          </div>
          <ComparisonFundusImage
            screeningId={previousScreeningId}
            eye={eye}
            mode={viewMode}
            targetClass={prevGrade ?? undefined}
            alt={`Prior ${eye} Fundus`}
          />
        </div>

        {/* Current Image */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-[#4a5320] flex items-center gap-1.5">
              <Calendar size={13} className="text-[#4a5320]" />
              Current Encounter ({new Date(currentDate).toLocaleDateString()})
            </span>
            <span className="font-mono text-[11px] font-bold text-[#1c1d1a]">
              {currGrade !== null && currGrade !== undefined ? `Grade ${currGrade} (${currLabel})` : 'No Result'}
            </span>
          </div>
          <ComparisonFundusImage
            screeningId={currentScreeningId}
            eye={eye}
            mode={viewMode}
            targetClass={currGrade ?? undefined}
            alt={`Current ${eye} Fundus`}
          />
        </div>
      </div>

      {/* Five-Class Probability Shifts */}
      {comparison.probability_shifts && Object.keys(comparison.probability_shifts).length > 0 && (
        <div className="bg-white rounded-xl p-3.5 border border-[#e8e4d8] space-y-2">
          <div className="flex items-center justify-between text-xs pb-1.5 border-b border-[#f0f2eb]">
            <span className="font-semibold text-[#1c1d1a] flex items-center gap-1.5">
              <Sliders size={13} className="text-[#6f7d3e]" />
              Five-Class Probability Distribution &amp; Progression Shift
            </span>
            {comparison.vtdr_risk_shift !== null && comparison.vtdr_risk_shift !== undefined && (
              <span className="font-mono text-[11px] text-[#5a5d52]">
                Referable DR Risk Shift:{' '}
                <strong className={comparison.vtdr_risk_shift > 0.05 ? 'text-amber-700' : 'text-[#1c1d1a]'}>
                  {comparison.vtdr_risk_shift > 0 ? `+${(comparison.vtdr_risk_shift * 100).toFixed(1)}%` : `${(comparison.vtdr_risk_shift * 100).toFixed(1)}%`}
                </strong>
              </span>
            )}
          </div>

          <div className="grid grid-cols-5 gap-2 text-center pt-1">
            {[0, 1, 2, 3, 4].map((g) => {
              const shift = comparison.probability_shifts?.[String(g)] ?? 0;
              const prevP = comparison.previous_probabilities?.[String(g)] ?? 0;
              const currP = comparison.current_probabilities?.[String(g)] ?? 0;
              const shiftColor =
                shift > 0.02
                  ? 'text-amber-700 bg-amber-50 border-amber-200'
                  : shift < -0.02
                  ? 'text-blue-700 bg-blue-50 border-blue-200'
                  : 'text-[#7a7d72] bg-[#faf9f5] border-[#e8e4d8]';

              return (
                <div key={g} className={`p-2 rounded-lg border text-xs ${shiftColor}`}>
                  <div className="font-bold text-[11px]">Grade {g}</div>
                  <div className="font-mono text-[10px] text-[#5a5d52] mt-0.5">
                    {(prevP * 100).toFixed(0)}% â†’ {(currP * 100).toFixed(0)}%
                  </div>
                  <div className="font-mono text-[11px] font-bold mt-0.5">
                    {shift > 0 ? `+${(shift * 100).toFixed(1)}%` : `${(shift * 100).toFixed(1)}%`}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Clinical Neutral Summary Banner */}
      <div className="p-3 bg-[#f2f4e8] border border-[#d8debe] rounded-xl text-xs text-[#2e3129] flex items-start gap-2">
        <Info size={14} className="text-[#4a5320] shrink-0 mt-0.5" />
        <span className="leading-relaxed">{comparison.neutral_summary}</span>
      </div>
    </div>
  );
}

export function ScreeningComparisonViewer({
  currentScreeningId,
  patientId,
  initialPreviousScreeningId,
  className = '',
}: ScreeningComparisonViewerProps) {
  const [patientScreenings, setPatientScreenings] = useState<ApiScreening[]>([]);
  const [selectedPriorId, setSelectedPriorId] = useState<string>(initialPreviousScreeningId || '');
  const [comparison, setComparison] = useState<ScreeningComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 1. Fetch patient's past screenings for selector dropdown
  useEffect(() => {
    let active = true;
    screeningApi
      .list({ patient_id: patientId, page_size: 50 })
      .then((res) => {
        if (!active) return;
        // Filter out current screening and cancelled ones
        const eligible = res.items.filter((s) => s.id !== currentScreeningId && s.status !== 'cancelled');
        setPatientScreenings(eligible);
        if (!selectedPriorId && eligible.length > 0) {
          setSelectedPriorId(eligible[0].id);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [patientId, currentScreeningId, selectedPriorId]);

  // 2. Fetch comparison response whenever selected prior changes
  useEffect(() => {
    let active = true;

    clinicalWorkflowApi
      .getScreeningComparison(currentScreeningId, selectedPriorId || undefined)
      .then((data) => {
        if (!active) return;
        setComparison(data);
        setError(null);
        if (!selectedPriorId && data.previous_screening_id) {
          setSelectedPriorId(data.previous_screening_id);
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Unable to load longitudinal comparison.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [currentScreeningId, selectedPriorId]);

  if (loading) {
    return (
      <div className={`p-8 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs text-center space-y-3 ${className}`}>
        <Loader2 size={22} className="animate-spin text-[#4a5320] mx-auto" />
        <p className="text-xs text-[#7a7d72] font-mono">
          Loading longitudinal comparison and bilateral Grad-CAM alignment...
        </p>
      </div>
    );
  }

  if (error || !comparison) {
    return (
      <div className={`p-6 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs text-center space-y-3 ${className}`}>
        <div className="w-10 h-10 rounded-full bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center mx-auto">
          <Info size={20} />
        </div>
        <h4 className="font-serif text-sm text-[#1c1d1a]">No Prior Screening for Direct Comparison</h4>
        <p className="text-xs text-[#7a7d72] max-w-md mx-auto leading-relaxed">
          {error || 'This encounter serves as the patient baseline or no earlier completed screenings exist for this patient record.'}
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Top Controller Bar */}
      <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-serif text-lg text-[#1c1d1a]">Longitudinal Screening Comparison</h3>
            <span className="px-2.5 py-0.5 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] text-xs font-mono font-semibold">
              {comparison.days_interval} days interval
            </span>
          </div>
          <p className="text-xs text-[#7a7d72] mt-0.5">
            Evaluating encounter <strong>{comparison.current_screening_reference}</strong> against prior encounter <strong>{comparison.previous_screening_reference}</strong>.
          </p>
        </div>

        {/* Prior Encounter Selector */}
        {patientScreenings.length > 1 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[#5a5d52] font-medium shrink-0">Compare Against:</span>
            <select
              value={selectedPriorId}
              onChange={(e) => setSelectedPriorId(e.target.value)}
              className="bg-[#faf9f5] border border-[#d8debe] rounded-full px-3 py-1.5 text-xs font-mono font-semibold text-[#1c1d1a] focus:outline-none focus:ring-1 focus:ring-[#4a5320] cursor-pointer"
            >
              {patientScreenings.map((sc) => (
                <option key={sc.id} value={sc.id}>
                  {sc.screening_reference} ({new Date(sc.created_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Model Comparability Banner if needed */}
      {!comparison.is_directly_comparable && comparison.comparability_notes.length > 0 && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-xs text-amber-900 flex items-start gap-2.5">
          <AlertTriangle size={16} className="text-amber-700 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-bold">Checkpoint Calibration Notice</div>
            {comparison.comparability_notes.map((note, idx) => (
              <p key={idx} className="leading-relaxed">{note}</p>
            ))}
          </div>
        </div>
      )}

      {/* Bilateral Comparison Cards: OD and OS */}
      <div className="space-y-5">
        <EyeComparisonCard
          eye="OD"
          comparison={comparison.od_comparison}
          currentScreeningId={comparison.current_screening_id}
          previousScreeningId={comparison.previous_screening_id}
          currentDate={comparison.current_screening_date}
          previousDate={comparison.previous_screening_date}
        />

        <EyeComparisonCard
          eye="OS"
          comparison={comparison.os_comparison}
          currentScreeningId={comparison.current_screening_id}
          previousScreeningId={comparison.previous_screening_id}
          currentDate={comparison.current_screening_date}
          previousDate={comparison.previous_screening_date}
        />
      </div>

      {/* Overall Longitudinal Summary Box */}
      <div className="p-4 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-2 text-xs">
        <div className="font-serif font-bold text-[#1c1d1a] flex items-center gap-2">
          <CheckCircle2 size={15} className="text-[#4a5320]" />
          Longitudinal AI Decision-Support Summary
        </div>
        <p className="text-[#5a5d52] leading-relaxed">
          {comparison.overall_comparison_summary}
        </p>
        <div className="pt-2 border-t border-[#f0f2eb] text-[11px] text-[#7a7d72] italic">
          {comparison.clinical_safety_disclaimer}
        </div>
      </div>
    </div>
  );
}
