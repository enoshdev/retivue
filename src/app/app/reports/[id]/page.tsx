'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import { clinicalWorkflowApi, screeningApi, ScreeningReportResponse } from '@/lib/api';
import { ScreeningComparisonViewer } from '@/components/clinical/ScreeningComparisonViewer';
import {
  ArrowLeft,
  Printer,
  Loader2,
  UserCheck,
  AlertTriangle,
  Sparkles,
  Download,
} from 'lucide-react';

const REPORT_PROB_CLASSES = [
  { key: 'class_0_no_dr', grade: 0, label: '0: No DR', barColor: 'bg-emerald-500' },
  { key: 'class_1_mild', grade: 1, label: '1: Mild NPDR', barColor: 'bg-blue-500' },
  { key: 'class_2_moderate', grade: 2, label: '2: Moderate NPDR', barColor: 'bg-amber-500' },
  { key: 'class_3_severe', grade: 3, label: '3: Severe NPDR', barColor: 'bg-orange-500' },
  { key: 'class_4_proliferative', grade: 4, label: '4: Proliferative DR', barColor: 'bg-rose-500' },
];

function SecureReportImage({
  screeningId,
  eye,
  kind,
}: {
  screeningId: string;
  eye: 'OD' | 'OS';
  kind: 'original' | 'overlay';
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    let url: string | null = null;
    const fetcher =
      kind === 'original'
        ? screeningApi.fetchImageBlobUrl(screeningId, eye)
        : clinicalWorkflowApi.fetchExplanationImageBlobUrl(screeningId, eye, 'overlay');

    fetcher
      .then((u) => {
        if (!active) {
          URL.revokeObjectURL(u);
          return;
        }
        url = u;
        setBlobUrl(u);
      })
      .catch(() => {
        if (active) setBlobUrl(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [screeningId, eye, kind]);

  if (loading) {
    return (
      <div className="w-full h-44 bg-[#0d0e11] rounded-lg border border-[#262a30] flex items-center justify-center text-[#8e9298] text-[10px] font-mono">
        <Loader2 size={13} className="animate-spin text-[#dee9a6] mr-1.5" />
        <span>Loading {kind === 'original' ? 'Fundus Scan' : 'Grad-CAM'}...</span>
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="w-full h-44 bg-[#0d0e11] rounded-lg border border-[#262a30] flex flex-col items-center justify-center text-[#8e9298] text-[10px] font-mono p-3 text-center">
        <span>{kind === 'original' ? 'Fundus Scan Unavailable' : 'Grad-CAM Overlay Not Generated'}</span>
      </div>
    );
  }

  return (
    <div className="relative w-full h-44 bg-black rounded-lg overflow-hidden border border-[#262a30] flex items-center justify-center">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={blobUrl}
        alt={`${eye} ${kind}`}
        className="w-full h-full object-contain pointer-events-none"
      />
    </div>
  );
}

export default function ScreeningSummaryReportPage() {
  const params = useParams();
  const screeningId = params?.id as string;

  const [report, setReport] = useState<ScreeningReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  const handleDownloadPdf = async () => {
    if (!report) return;
    setIsDownloadingPdf(true);
    try {
      await clinicalWorkflowApi.downloadReportPdf(report.screening_id);
    } catch {
      // ignore
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  useEffect(() => {
    let active = true;
    clinicalWorkflowApi
      .getScreeningReport(screeningId)
      .then((res) => {
        if (active) {
          setReport(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unable to load clinical screening report.');
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [screeningId]);

  if (loading) {
    return (
      <div className="p-16 text-center text-xs text-[#7a7d72] flex items-center justify-center gap-2">
        <Loader2 size={18} className="animate-spin text-[#4a5320]" />
        <span>Generating integrated clinical screening report...</span>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="p-12 text-center bg-white border border-[#e8e4d8] rounded-2xl max-w-lg mx-auto my-12 shadow-xs">
        <h2 className="text-base font-bold font-serif text-[#1c1d1a] mb-1">Report Not Found</h2>
        <p className="text-xs text-[#7a7d72] mb-5 leading-relaxed">
          {error || `No screening report matching ${screeningId} was found under your account.`}
        </p>
        <Link
          href="/app/reports"
          className="inline-flex items-center gap-1.5 bg-[#4a5320] text-white text-xs font-semibold px-4 py-2 rounded-full no-underline hover:bg-[#3e461a] transition-colors"
        >
          <ArrowLeft size={13} />
          <span>Return to Reports</span>
        </Link>
      </div>
    );
  }

  const ai = report.latest_ai_run;
  const review = report.clinical_review;

  return (
    <div className="space-y-6 pb-20 max-w-4xl mx-auto select-none">
      <div className="flex items-center justify-between pb-4 border-b border-[#e8e4d8] print:hidden">
        <Link
          href={`/app/screenings/${report.screening_id}`}
          className="inline-flex items-center gap-1.5 text-xs text-[#6f7d3e] hover:text-[#4a5320] transition-colors no-underline font-medium"
        >
          <ArrowLeft size={14} />
          <span>Back to Screening Encounter</span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={isDownloadingPdf}
            className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs hover:shadow cursor-pointer disabled:opacity-50"
          >
            {isDownloadingPdf ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            <span>Download Official PDF</span>
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 bg-[#f2f4e8] hover:bg-[#e4ebc8] text-[#4a5320] border border-[#d8debe] px-5 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs hover:shadow cursor-pointer"
          >
            <Printer size={15} />
            <span>Print Report</span>
          </button>
        </div>
      </div>

      <div className="bg-white border border-[#e8e4d8] rounded-2xl p-8 sm:p-12 space-y-7 shadow-sm print:border-none print:shadow-none print:p-0">
        {/* Header */}
        <div className="flex items-start justify-between pb-6 border-b-2 border-[#4a5320]">
          <div>
            <RetivueLogo size="md" variant="olive" href="/app" />
            <div className="text-[11px] font-mono text-[#7a7d72] mt-1.5 uppercase tracking-wider">
              Comprehensive Clinical Screening &amp; Decision-Support Report
            </div>
          </div>

          <div className="text-right text-xs font-mono">
            <div className="font-bold text-[#1c1d1a] text-sm">{report.report_id}</div>
            <div className="text-[#7a7d72] mt-0.5">
              Encounter: <span className="font-semibold text-[#1c1d1a]">{report.screening_reference}</span>
            </div>
            <div className="text-[#7a7d72] mt-0.5">
              Generated: {new Date(report.generated_at).toLocaleDateString()}
            </div>
            <div className="mt-1">
              <StatusBadge type="status" value={report.screening_status} size="sm" />
            </div>
          </div>
        </div>

        {/* Patient Demographics & Consent */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl p-5 text-xs">
          <div className="space-y-1.5">
            <h4 className="font-mono uppercase font-bold text-[#4a5320] text-[11px] tracking-wider mb-2">
              Patient Beneficiary
            </h4>
            <div className="text-sm font-bold font-serif text-[#1c1d1a]">{report.patient.full_name}</div>
            <div className="text-[#5a5d52]">
              MRN / Clinic ID: <span className="font-mono font-semibold text-[#1c1d1a]">{report.patient.medical_record_number || 'N/A'}</span>
            </div>
            <div className="text-[#5a5d52]">
              DOB: {report.patient.date_of_birth || 'N/A'} • Sex: {report.patient.gender || 'N/A'}
            </div>
            <div className="text-[#5a5d52]">
              Diabetes Type: <span className="font-medium text-[#1c1d1a]">{report.patient.diabetes_type || 'Unspecified'}</span>
            </div>
          </div>

          <div className="space-y-1.5 border-t md:border-t-0 md:border-l border-[#e8e4d8] md:pl-6 pt-4 md:pt-0">
            <h4 className="font-mono uppercase font-bold text-[#4a5320] text-[11px] tracking-wider mb-2">
              Consent &amp; Ingestion Governance
            </h4>
            <div className="flex items-center gap-1.5">
              <span className="text-[#5a5d52]">Informed Consent Status:</span>
              <span
                className={`font-semibold font-mono px-2 py-0.5 rounded-full text-[10px] ${
                  report.consent.status === 'granted'
                    ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                    : 'bg-rose-100 text-rose-900 border border-rose-300'
                }`}
              >
                {report.consent.status.toUpperCase()}
              </span>
            </div>
            <div className="text-[#7a7d72]">
              Captured: {report.consent.obtained_at ? new Date(report.consent.obtained_at).toLocaleString() : 'Recorded'}
            </div>
            <div className="text-[#7a7d72]">
              Bilateral Images Captured: {report.images.length} verified original frames
            </div>
          </div>
        </div>

        {/* Professional Clinical Assessment (Primary Sovereign Record) */}
        <div className="border border-[#d8debe] bg-[#f2f4e8]/60 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-[#d8debe] pb-2">
            <div className="flex items-center gap-2">
              <UserCheck size={18} className="text-[#4a5320]" />
              <h3 className="font-bold text-sm text-[#1c1d1a]">
                Qualified Professional Clinical Assessment
              </h3>
            </div>
            {review?.is_signed && (
              <span className="font-mono text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300">
                Digitally Signed &amp; Locked
              </span>
            )}
          </div>

          {review ? (
            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-white border border-[#d8debe] rounded-lg p-3">
                <div>
                  <div className="text-[11px] text-[#7a7d72] uppercase font-mono">Signatory</div>
                  <div className="font-bold text-[#1c1d1a] mt-0.5">{review.reviewer_name_snapshot}</div>
                  <div className="font-mono text-[11px] text-[#4a5320]">{review.reviewer_registration_number_snapshot}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#7a7d72] uppercase font-mono">Confirmed DR Severity</div>
                  <div className="font-bold text-[#1c1d1a] text-sm mt-0.5">
                    {review.worst_eye_confirmed_label ? review.worst_eye_confirmed_label.replace(/_/g, ' ') : 'Recapture Required'}
                  </div>
                  <div className="text-[11px] text-[#7a7d72]">
                    OD: Grade {review.od_confirmed_grade ?? '—'} • OS: Grade {review.os_confirmed_grade ?? '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-[#7a7d72] uppercase font-mono">AI Agreement</div>
                  <div className="font-mono font-medium text-[#1c1d1a] mt-0.5">
                    {review.ai_agreement_status.replace(/_/g, ' ').toUpperCase()}
                  </div>
                  <div className="text-[11px] text-[#7a7d72]">
                    Signed: {new Date(review.signed_at).toLocaleString()}
                  </div>
                </div>
              </div>

              {review.override_rationale && (
                <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
                  <span className="font-bold font-mono text-[11px]">CLINICAL OVERRIDE RATIONALE: </span>
                  <span>{review.override_rationale}</span>
                </div>
              )}

              <div className="space-y-1">
                <span className="font-mono font-bold text-[11px] uppercase text-[#4a5320]">Clinical Findings:</span>
                <p className="text-[#1c1d1a] leading-relaxed bg-white border border-[#e8e4d8] rounded-lg p-3">
                  {review.clinical_findings}
                </p>
              </div>

              <div className="space-y-1">
                <span className="font-mono font-bold text-[11px] uppercase text-[#4a5320]">Management &amp; Follow-up Plan:</span>
                <p className="text-[#1c1d1a] leading-relaxed bg-white border border-[#e8e4d8] rounded-lg p-3">
                  {review.follow_up_plan}
                </p>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-700 shrink-0" />
              <span>Independent clinical review is currently pending. Only credentialed practitioners may sign off findings.</span>
            </div>
          )}
        </div>

        {/* Research Decision Support (AI Advisory Output & Genuine Grad-CAM) */}
        {ai && (
          <div className="border border-[#e8e4d8] rounded-xl p-5 space-y-5 bg-white">
            <div className="flex items-center justify-between border-b border-[#e8e4d8] pb-2">
              <h3 className="font-bold text-sm text-[#1c1d1a] flex items-center gap-2">
                <Sparkles size={16} className="text-[#4a5320]" />
                <span>AI Screening Advisory &amp; Grad-CAM Visual Explainability</span>
                <span className="text-[10px] font-mono text-[#7a7d72] bg-[#f5f3ec] px-2 py-0.5 rounded-full border border-[#e8e4d8]">
                  {ai.model_key}
                </span>
              </h3>
              <span
                className={`text-[10px] font-mono font-semibold px-2.5 py-0.5 rounded-full ${
                  ai.overall_status === 'quality_failed'
                    ? 'bg-amber-100 text-amber-900 border border-amber-300'
                    : ai.overall_review_required
                    ? 'bg-amber-50 text-amber-900 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                }`}
              >
                {ai.overall_status.toUpperCase()}
              </span>
            </div>

            {/* Bilateral Summary */}
            <div className="p-3 bg-[#f5f3ec] border border-[#e8e4d8] rounded-xl text-xs text-[#5a5d52] flex flex-wrap items-center justify-between gap-2">
              <div>
                <strong>Bilateral Analysis:</strong> Higher Risk Eye: <span className="font-bold text-[#1c1d1a]">{ai.higher_risk_eye || 'Equal/Bilateral'}</span> • Highest DR Severity: <span className="font-bold text-[#4a5320]">{ai.highest_predicted_label?.replace(/_/g, ' ') || 'None'}</span>
              </div>
              <div className="font-mono text-[10px] text-[#7a7d72]">
                Target Architecture: EfficientNet-B0 (Layer: features[8])
              </div>
            </div>

            {/* Bilateral Retinal Image & Explainability Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
              {ai.eye_results.map((eye) => {
                const explanation = eye.explanation || report.explanations?.[eye.eye];

                return (
                  <div key={eye.id} className="p-4 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl space-y-3.5">
                    <div className="flex items-center justify-between font-bold text-[#1c1d1a]">
                      <span className="font-mono text-sm">{eye.eye === 'OD' ? 'Right Eye (OD)' : 'Left Eye (OS)'}</span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                          eye.gradable ? 'bg-emerald-100 text-emerald-900' : 'bg-rose-100 text-rose-900'
                        }`}
                      >
                        {eye.gradable ? 'Gradable Quality' : 'Ungradable Quality'}
                      </span>
                    </div>

                    {/* Dual Fundus Imagery: Original & Grad-CAM Overlay */}
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <span className="text-[10px] font-mono text-[#7a7d72] uppercase block">Original Fundus</span>
                        <SecureReportImage screeningId={report.screening_id} eye={eye.eye} kind="original" />
                      </div>
                      <div className="space-y-1">
                        <span className="text-[10px] font-mono text-[#4a5320] uppercase font-bold block">Grad-CAM Overlay</span>
                        <SecureReportImage screeningId={report.screening_id} eye={eye.eye} kind="overlay" />
                      </div>
                    </div>

                    {eye.gradable ? (
                      <>
                        <div className="flex items-baseline justify-between border-b border-[#e8e4d8] pb-1.5 pt-1">
                          <div className="text-sm font-serif font-bold text-[#4a5320]">
                            {eye.predicted_label?.replace(/_/g, ' ') || 'Ungraded'}
                          </div>
                          <div className="text-[11px] font-mono font-semibold text-[#1c1d1a]">
                            Confidence: {((eye.confidence_max_prob || 0) * 100).toFixed(1)}%
                          </div>
                        </div>

                        {/* 5-Class Probability Distribution */}
                        <div className="space-y-1 font-mono">
                          <div className="text-[10px] uppercase text-[#7a7d72] font-semibold">
                            Probability Distribution:
                          </div>
                          {REPORT_PROB_CLASSES.map((cls) => {
                            const p = eye.probabilities[cls.key] ??
                              eye.probabilities[Object.keys(eye.probabilities).find(k => k.startsWith(`class_${cls.grade}`)) || ''] ??
                              0;
                            const pct = (p * 100).toFixed(1);
                            const isTop = eye.predicted_grade === cls.grade;

                            return (
                              <div key={cls.key} className="space-y-0.5">
                                <div className="flex justify-between text-[10px]">
                                  <span className={isTop ? 'font-bold text-[#1c1d1a]' : 'text-[#7a7d72]'}>{cls.label}</span>
                                  <span className={isTop ? 'font-bold text-[#4a5320]' : 'text-[#7a7d72]'}>{pct}%</span>
                                </div>
                                <div className="w-full bg-[#e8e4d8] rounded-full h-1 overflow-hidden">
                                  <div
                                    className={`${cls.barColor} h-1 rounded-full`}
                                    style={{ width: `${Math.max(Number(pct), 1)}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {/* Metrics Table */}
                        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-[#7a7d72] bg-white p-2 rounded border border-[#e8e4d8]">
                          <div>Top-2 Margin: <span className="text-[#1c1d1a] font-semibold">{((eye.top2_margin || 0) * 100).toFixed(1)}%</span></div>
                          <div>Entropy: <span className="text-[#1c1d1a] font-semibold">{eye.normalized_entropy?.toFixed(3) || '—'}</span></div>
                          <div>VTDR Risk: <span className="text-[#1c1d1a] font-semibold">{((eye.vtdr_prob_sum || 0) * 100).toFixed(1)}%</span></div>
                          <div>Review Required: <span className={eye.uncertainty_review_required ? 'text-amber-800 font-bold' : 'text-emerald-800 font-semibold'}>{eye.uncertainty_review_required ? 'YES' : 'NO'}</span></div>
                        </div>

                        {/* Clinical Narrative Explanation */}
                        {explanation?.explanation_text && (
                          <div className="p-2.5 bg-white rounded-lg border border-[#e8e4d8] text-[11px] text-[#2e3129] leading-relaxed space-y-1">
                            <div className="font-bold font-mono text-[10px] uppercase text-[#4a5320] flex items-center gap-1">
                              <Sparkles size={11} />
                              <span>Clinical Explainability Narrative:</span>
                            </div>
                            <p className="whitespace-pre-line text-[#3f4339]">{explanation.explanation_text}</p>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-xs text-rose-800 font-mono p-2 bg-rose-50 rounded border border-rose-200">
                        Reason for refusal: {eye.quality_reason || 'Failed quality threshold.'}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="p-3 bg-[#f5f3ec] border border-[#e8e4d8] rounded-lg text-[11px] text-[#5a5d52] leading-relaxed">
              <strong>Provenance:</strong> Checkpoint SHA-256: <span className="font-mono text-[#1c1d1a]">{ai.checkpoint_sha256}</span> • Epoch {ai.checkpoint_epoch} • Evaluated in {ai.execution_ms}ms.
              <div className="mt-1 text-[#7a7d72]">{ai.research_disclaimer}</div>
            </div>
          </div>
        )}

        {/* Specialist Referrals */}
        {report.referrals.length > 0 && (
          <div className="border border-[#e8e4d8] rounded-xl p-5 space-y-3 bg-white">
            <h3 className="font-bold text-sm text-[#1c1d1a]">Dispatched Specialist Referrals</h3>
            <div className="space-y-2 text-xs">
              {report.referrals.map((ref) => (
                <div key={ref.id} className="p-3 bg-[#faf9f5] border border-[#e8e4d8] rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <span className="font-mono font-bold text-[#1c1d1a]">{ref.referral_reference}</span>
                    <span className="mx-2">•</span>
                    <span className="font-semibold text-[#4a5320]">{ref.target_facility}</span> ({ref.target_specialty})
                    <div className="text-[#7a7d72] mt-0.5">{ref.reason_summary}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-900 border border-rose-300">
                      {ref.urgency.replace(/_/g, ' ')}
                    </span>
                    <div className="text-[10px] font-mono text-[#7a7d72] mt-1">Status: {ref.status}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Chronological Audit Trail */}
        <div className="border-t border-[#e8e4d8] pt-5 space-y-3">
          <h4 className="font-mono uppercase font-bold text-[#7a7d72] text-[11px] tracking-wider">
            Traceable Clinical Audit Trail
          </h4>
          <div className="space-y-1.5 font-mono text-[11px]">
            {report.audit_trail.map((entry) => (
              <div key={entry.id} className="flex items-start justify-between p-2 rounded-md bg-[#faf9f5] border border-[#f0eee6]">
                <div className="space-y-0.5">
                  <span className="font-bold text-[#4a5320] mr-2">[{entry.event_type}]</span>
                  <span className="text-[#1c1d1a]">{entry.summary}</span>
                </div>
                <span className="text-[#7a7d72] shrink-0 ml-3">
                  {new Date(entry.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Safety Notice */}
        <div className="p-4 bg-[#f5f3ec] border border-[#e8e4d8] rounded-xl text-[11px] text-[#5a5d52] leading-relaxed">
          <div className="font-bold uppercase text-[#1c1d1a] mb-1 font-mono">Mandatory Clinical Safety Notice</div>
          <p>{report.clinical_safety_notice}</p>
        </div>
      </div>

      {/* Longitudinal Comparison Against Prior Encounter */}
      <div className="print:hidden space-y-3">
        <h3 className="font-serif text-base text-[#1c1d1a] px-1">Longitudinal Encounter Comparison</h3>
        <ScreeningComparisonViewer
          currentScreeningId={report.screening_id}
          patientId={report.patient.id}
        />
      </div>
    </div>
  );
}
