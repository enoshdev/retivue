'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useClinical } from '@/context/ClinicalContext';
import {
  ApiScreening,
  ApiScreeningImage,
  screeningApi,
  clinicalWorkflowApi,
  AiRunResponse,
  ClinicalReviewResponse,
  ReferralResponse,
} from '@/lib/api';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import { FundusViewer } from '@/components/clinical/FundusViewer';
import { ScreeningComparisonViewer } from '@/components/clinical/ScreeningComparisonViewer';
import {
  ArrowLeft,
  Eye,
  Loader2,
  AlertTriangle,
  UploadCloud,
  Replace,
  ArrowRight,
  Sparkles,
  FileCheck,
  FileText,
  Send,
  UserCheck,
  Download,
  GitCompare,
} from 'lucide-react';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function extractEyeProb(probabilities: Record<string, number> | undefined, grade: number): number {
  if (!probabilities) return 0;
  if (probabilities[String(grade)] !== undefined) return Number(probabilities[String(grade)]);
  if (probabilities[grade] !== undefined) return Number(probabilities[grade]);
  const tokenMap: Record<number, string[]> = {
    0: ['no_dr', 'nodr', 'class_0'],
    1: ['mild', 'class_1'],
    2: ['moderate', 'class_2'],
    3: ['severe', 'class_3'],
    4: ['proliferative', 'pdr', 'class_4'],
  };
  const tokens = tokenMap[grade] || [];
  for (const [k, v] of Object.entries(probabilities)) {
    const lk = k.toLowerCase().replace(/[^a-z0-9]/g, '_');
    if (tokens.some((tok) => lk.includes(tok))) {
      return Number(v);
    }
  }
  return 0;
}

const DR_PROB_CLASSES = [
  { key: 'class_0_no_dr', grade: 0, label: '0: No DR', barColor: 'bg-emerald-500' },
  { key: 'class_1_mild', grade: 1, label: '1: Mild NPDR', barColor: 'bg-blue-500' },
  { key: 'class_2_moderate', grade: 2, label: '2: Moderate NPDR', barColor: 'bg-amber-500' },
  { key: 'class_3_severe', grade: 3, label: '3: Severe NPDR', barColor: 'bg-orange-500' },
  { key: 'class_4_proliferative', grade: 4, label: '4: Proliferative DR', barColor: 'bg-rose-500' },
];

export default function ScreeningInspectionWorkspacePage() {
  const params = useParams();
  const screeningId = params?.id as string;

  const { fetchScreeningById, upsertScreeningInCache, setNotification } = useClinical();

  const [screening, setScreening] = useState<ApiScreening | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [activeEye, setActiveEye] = useState<'OD' | 'OS'>('OD');
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [redFreeFilter, setRedFreeFilter] = useState<boolean>(false);

  // Live upload/replace/submit controls
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [imageHistory, setImageHistory] = useState<ApiScreeningImage[]>([]);

  // Phase 12 AI & Clinical Workflow State
  const [aiRun, setAiRun] = useState<AiRunResponse | null>(null);
  const [clinicalReview, setClinicalReview] = useState<ClinicalReviewResponse | null>(null);
  const [referrals, setReferrals] = useState<ReferralResponse[]>([]);
  const [isRunningAi, setIsRunningAi] = useState<boolean>(false);
  const [isSigningReview, setIsSigningReview] = useState<boolean>(false);
  const [isCreatingReferral, setIsCreatingReferral] = useState<boolean>(false);
  const [showReferralModal, setShowReferralModal] = useState<boolean>(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState<boolean>(false);
  const [showComparison, setShowComparison] = useState<boolean>(false);

  // Review Form state
  const [odGrade, setOdGrade] = useState<number | ''>('');
  const [osGrade, setOsGrade] = useState<number | ''>('');
  const [agreementStatus, setAgreementStatus] = useState<
    'agreed_with_ai' | 'overrode_ai' | 'independent_no_ai' | 'recapture_ordered'
  >('independent_no_ai');
  const [overrideRationale, setOverrideRationale] = useState('');
  const [findingsText, setFindingsText] = useState('');
  const [followUpPlan, setFollowUpPlan] = useState('');
  const [recaptureRequired, setRecaptureRequired] = useState(false);
  const [confirmIndependent, setConfirmIndependent] = useState(false);

  // Referral Form state
  const [refUrgency, setRefUrgency] = useState<'IMMEDIATE_48H' | 'WITHIN_2_WEEKS' | 'STANDARD_SURVEILLANCE'>(
    'WITHIN_2_WEEKS'
  );
  const [refFacility, setRefFacility] = useState('Apex Eye Institute');
  const [refSpecialty, setRefSpecialty] = useState('Medical Retina & Vitreoretinal Surgery');
  const [refReason, setRefReason] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const reloadWorkflowState = async (sid: string) => {
    try {
      const [latestAi, rev, refs] = await Promise.all([
        clinicalWorkflowApi.getLatestAiRun(sid).catch(() => null),
        clinicalWorkflowApi.getClinicalReview(sid).catch(() => null),
        clinicalWorkflowApi.listReferrals(sid).catch(() => []),
      ]);
      setAiRun(latestAi);
      setClinicalReview(rev);
      setReferrals(refs);
      if (latestAi && !rev) {
        setAgreementStatus('agreed_with_ai');
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    let active = true;
    fetchScreeningById(screeningId)
      .then((data) => {
        if (!active) return;
        if (!data) {
          setError('Screening encounter not found or you are not authorized to access it.');
        } else {
          setScreening(data);
          if (!data.has_od_image && data.has_os_image) {
            setActiveEye('OS');
          }
          setError(null);
          reloadWorkflowState(data.id);
        }
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Unable to load screening workspace.');
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [screeningId, fetchScreeningById]);

  // Fetch replacement audit history for the currently selected eye
  useEffect(() => {
    let active = true;
    if (!screening) return;
    screeningApi
      .getImageHistory(screening.id, activeEye)
      .then((hist) => {
        if (active) setImageHistory(hist);
      })
      .catch(() => {
        if (active) setImageHistory([]);
      });
    return () => {
      active = false;
    };
  }, [screening, activeEye]);

  const handleUploadOrReplace = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !screening) return;

    const existingForEye = activeEye === 'OD' ? screening.od_image : screening.os_image;
    const isReplace = Boolean(existingForEye);

    setActionError(null);
    setUploadProgress(0);
    try {
      if (isReplace) {
        await screeningApi.replaceImage(screening.id, activeEye, file, (pct) => setUploadProgress(pct));
        setNotification({
          type: 'success',
          message: `${activeEye} retinal image replaced securely. Audit history preserved.`,
        });
      } else {
        await screeningApi.uploadImage(screening.id, activeEye, file, (pct) => setUploadProgress(pct));
        setNotification({
          type: 'success',
          message: `${activeEye} retinal image uploaded and verified successfully.`,
        });
      }

      const refreshed = await screeningApi.get(screening.id);
      setScreening(refreshed);
      upsertScreeningInCache(refreshed);

      const hist = await screeningApi.getImageHistory(screening.id, activeEye);
      setImageHistory(hist);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed.';
      setActionError(msg);
      setNotification({ type: 'error', message: msg });
    } finally {
      setUploadProgress(null);
    }
  };

  const handleSubmitScreening = async () => {
    if (!screening) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      const updated = await screeningApi.submit(screening.id);
      setScreening(updated);
      upsertScreeningInCache(updated);
      setNotification({
        type: 'success',
        message: 'Encounter submitted for Quality Assessment and AI Screening.',
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Submission failed.';
      setActionError(msg);
      setNotification({ type: 'error', message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRunAiAnalysis = async () => {
    if (!screening) return;
    setIsRunningAi(true);
    setActionError(null);
    try {
      const runRes = await clinicalWorkflowApi.runAiScreening(screening.id);
      setAiRun(runRes);
      const refreshed = await screeningApi.get(screening.id);
      setScreening(refreshed);
      upsertScreeningInCache(refreshed);
      setNotification({
        type: 'success',
        message: `AI screening analysis completed (Status: ${runRes.overall_status}).`,
      });
      reloadWorkflowState(screening.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'AI execution failed.';
      setActionError(msg);
      setNotification({ type: 'error', message: msg });
    } finally {
      setIsRunningAi(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!screening) return;
    setIsDownloadingPdf(true);
    setActionError(null);
    try {
      await clinicalWorkflowApi.downloadReportPdf(screening.id);
      setNotification({
        type: 'success',
        message: 'Official screening PDF report downloaded successfully.',
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'PDF generation failed.';
      setActionError(msg);
      setNotification({ type: 'error', message: msg });
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  const handleSignClinicalReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!screening) return;
    if (!confirmIndependent) {
      setActionError('You must confirm independent clinical review before signing off.');
      return;
    }
    setIsSigningReview(true);
    setActionError(null);
    try {
      const rev = await clinicalWorkflowApi.createClinicalReview(screening.id, {
        od_confirmed_grade: odGrade === '' ? null : Number(odGrade),
        os_confirmed_grade: osGrade === '' ? null : Number(osGrade),
        ai_agreement_status: agreementStatus,
        override_rationale: overrideRationale.trim() || null,
        clinical_findings: findingsText.trim(),
        follow_up_plan: followUpPlan.trim(),
        recapture_required: recaptureRequired,
        confirm_independent_review: confirmIndependent,
      });
      setClinicalReview(rev);
      const refreshed = await screeningApi.get(screening.id);
      setScreening(refreshed);
      upsertScreeningInCache(refreshed);
      setNotification({
        type: 'success',
        message: 'Clinical assessment digitally signed and locked.',
      });
      reloadWorkflowState(screening.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Review sign-off failed.';
      setActionError(msg);
      setNotification({ type: 'error', message: msg });
    } finally {
      setIsSigningReview(false);
    }
  };

  const handleCreateReferral = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!screening) return;
    setIsCreatingReferral(true);
    setActionError(null);
    try {
      const newRef = await clinicalWorkflowApi.createReferral({
        screening_id: screening.id,
        urgency: refUrgency,
        target_specialty: refSpecialty.trim(),
        target_facility: refFacility.trim(),
        reason_summary: refReason.trim(),
      });
      setReferrals([newRef, ...referrals]);
      setShowReferralModal(false);
      setRefReason('');
      setNotification({
        type: 'success',
        message: `Specialist referral ${newRef.referral_reference} dispatched successfully.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Referral dispatch failed.';
      setActionError(msg);
      setNotification({ type: 'error', message: msg });
    } finally {
      setIsCreatingReferral(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 text-center text-xs text-[#7a7d72] flex flex-col items-center justify-center gap-3">
        <Loader2 size={24} className="animate-spin text-[#4a5320]" />
        <span>Loading screening encounter from PostgreSQL...</span>
      </div>
    );
  }

  if (error || !screening) {
    return (
      <div className="p-12 text-center bg-white border border-[#e8e4d8] rounded-2xl max-w-lg mx-auto my-12 shadow-xs">
        <AlertTriangle size={28} className="text-amber-600 mx-auto mb-3" />
        <h2 className="text-base font-bold font-serif text-[#1c1d1a] mb-1">Screening Case Not Found</h2>
        <p className="text-xs text-[#7a7d72] mb-5 leading-relaxed">
          {error || `The requested screening record (${screeningId}) does not exist or belongs to another account.`}
        </p>
        <Link
          href="/app/screenings"
          className="inline-flex items-center gap-2 bg-[#4a5320] text-white text-xs font-semibold px-4 py-2.5 rounded-full no-underline hover:bg-[#3e461a] transition-colors shadow-xs"
        >
          <ArrowLeft size={14} />
          <span>Return to Screening History</span>
        </Link>
      </div>
    );
  }

  const patient = screening.patient;
  const currentEyeData = activeEye === 'OD' ? screening.od_image : screening.os_image;
  const activeEyeResult = aiRun?.eye_results?.find((e) => e.eye === activeEye);
  const consentGranted = patient?.consent_status === 'granted';
  const canModifyImages = screening.status !== 'cancelled' && screening.status !== 'archived' && !clinicalReview;
  const canSubmitForQA =
    screening.is_bilateral_complete &&
    consentGranted &&
    screening.status === 'draft' &&
    canModifyImages;
  const canRunAi =
    screening.is_bilateral_complete &&
    consentGranted &&
    !clinicalReview &&
    screening.status !== 'cancelled' &&
    screening.status !== 'archived';

  return (
    <div className="space-y-4 pb-16 select-none max-w-7xl mx-auto">
      {/* 1. TOP PATIENT HEADER RIBBON */}
      <div className="bg-white border border-[#e8e4d8] rounded-2xl p-4 sm:p-5 shadow-xs">
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5 min-w-0">
            <Link
              href="/app/screenings"
              className="p-2 text-[#7a7d72] hover:text-[#1c1d1a] hover:bg-[#f5f3ec] rounded-full transition-colors no-underline shrink-0"
              title="Return to Screening History"
            >
              <ArrowLeft size={18} />
            </Link>

            <div className="w-12 h-12 rounded-full bg-[#4a5320] text-white flex items-center justify-center font-serif text-lg font-bold shrink-0">
              {(patient?.full_name || 'P').charAt(0)}
            </div>

            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2.5 flex-wrap">
                <Link
                  href={`/app/patients/${screening.patient_id}`}
                  className="font-serif text-xl sm:text-2xl text-[#1c1d1a] hover:text-[#4a5320] no-underline font-bold truncate"
                >
                  {patient?.full_name || 'Patient Record'}
                </Link>
                {patient?.patient_code && (
                  <span className="font-mono text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] shrink-0">
                    {patient.patient_code}
                  </span>
                )}
                <StatusBadge type="status" value={screening.status} />
              </div>

              <div className="text-xs text-[#5a5d52] flex items-center gap-3 flex-wrap">
                <span className="font-mono font-medium text-[#1c1d1a]">{screening.screening_reference}</span>
                <span className="text-[#c8caba]">•</span>
                <span>{new Date(screening.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })} at {new Date(screening.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                {patient?.diabetes_type && (
                  <>
                    <span className="text-[#c8caba]">•</span>
                    <span>{patient.diabetes_type}</span>
                  </>
                )}
                {patient?.recent_hba1c && (
                  <>
                    <span className="text-[#c8caba]">•</span>
                    <span>HbA1c: <strong>{patient.recent_hba1c}</strong></span>
                  </>
                )}
                {screening.camera_model && (
                  <>
                    <span className="text-[#c8caba]">•</span>
                    <span className="text-[#7a7d72]">{screening.camera_model.split('(')[0].trim()}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <button
              type="button"
              onClick={() => setShowComparison(!showComparison)}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-full transition-colors shadow-2xs cursor-pointer ${
                showComparison
                  ? 'bg-[#4a5320] text-white'
                  : 'text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] hover:bg-[#e4ebc8]'
              }`}
            >
              <GitCompare size={13} />
              <span>{showComparison ? 'Hide Comparison' : 'Prior Comparison'}</span>
            </button>
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isDownloadingPdf}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-[#4a5320] hover:bg-[#3e461a] rounded-full transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {isDownloadingPdf ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
              <span>Download PDF</span>
            </button>
            <Link
              href={`/app/reports/${screening.id}`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] hover:bg-[#e4ebc8] rounded-full transition-colors no-underline shadow-2xs"
            >
              <FileText size={13} />
              <span>Clinical Report</span>
            </Link>
          </div>
        </div>
      </div>

      {actionError && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2">
          <AlertTriangle size={15} className="text-rose-600 shrink-0 mt-0.5" />
          <span>{actionError}</span>
        </div>
      )}

      {/* 2. MAIN WORKSPACE GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT / CENTER VIEWPORT (8 cols) */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-4">
          <div className="bg-white border border-[#e8e4d8] rounded-2xl p-4 shadow-xs space-y-3">
            {/* Viewport Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#e8e4d8]">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveEye('OD')}
                  className={`px-4 py-1.5 rounded-full text-xs font-mono font-semibold transition-all cursor-pointer ${
                    activeEye === 'OD'
                      ? 'bg-[#4a5320] text-white shadow-xs'
                      : 'bg-[#faf9f5] text-[#5a5d52] hover:bg-[#f5f3ec] border border-[#e8e4d8]'
                  }`}
                >
                  Right Eye (OD) {screening.has_od_image ? '✓' : '• Pending'}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveEye('OS')}
                  className={`px-4 py-1.5 rounded-full text-xs font-mono font-semibold transition-all cursor-pointer ${
                    activeEye === 'OS'
                      ? 'bg-[#4a5320] text-white shadow-xs'
                      : 'bg-[#faf9f5] text-[#5a5d52] hover:bg-[#f5f3ec] border border-[#e8e4d8]'
                  }`}
                >
                  Left Eye (OS) {screening.has_os_image ? '✓' : '• Pending'}
                </button>
              </div>

              {/* Viewport adjustment controls */}
              <div className="flex items-center gap-2 text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setRedFreeFilter(!redFreeFilter)}
                  className={`px-3 py-1 rounded-full border text-[11px] font-semibold transition-colors cursor-pointer ${
                    redFreeFilter
                      ? 'bg-emerald-900 text-emerald-100 border-emerald-950'
                      : 'bg-[#faf9f5] text-[#5a5d52] border-[#e8e4d8] hover:bg-[#f5f3ec]'
                  }`}
                >
                  Green / Red-Free
                </button>

                <div className="flex items-center gap-1 bg-[#faf9f5] border border-[#e8e4d8] rounded-full px-2 py-0.5">
                  <span className="text-[10px] text-[#7a7d72]">Zoom:</span>
                  <button
                    type="button"
                    onClick={() => setZoomLevel((z) => Math.max(0.75, z - 0.25))}
                    className="px-1 text-xs hover:text-[#4a5320] font-bold"
                  >
                    -
                  </button>
                  <span className="text-[11px] font-bold text-[#1c1d1a]">{Math.round(zoomLevel * 100)}%</span>
                  <button
                    type="button"
                    onClick={() => setZoomLevel((z) => Math.min(3, z + 0.25))}
                    className="px-1 text-xs hover:text-[#4a5320] font-bold"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>

            {/* Fundus Canvas / Explainability Workspace */}
            {currentEyeData ? (
              <FundusViewer
                screeningId={screening.id}
                eye={activeEye}
                patientRef={screening.screening_reference}
                explanation={activeEyeResult?.explanation || null}
                probabilities={activeEyeResult?.probabilities || {}}
                predictedGrade={activeEyeResult?.predicted_grade}
                predictedLabel={activeEyeResult?.predicted_label}
                gradable={activeEyeResult?.gradable ?? true}
                qualityReason={activeEyeResult?.quality_reason}
                onExplanationUpdate={() => reloadWorkflowState(screening.id)}
                className="w-full"
              />
            ) : (
              <div className="relative bg-[#1c1d1a] rounded-xl overflow-hidden min-h-[380px] sm:min-h-[460px] flex items-center justify-center border border-[#2e3129]">
                <div className="text-center p-8 text-[#edebe1] space-y-3">
                  <Eye size={36} className="mx-auto text-[#6f7d3e] opacity-60" />
                  <p className="text-sm font-serif">No retinal image uploaded for {activeEye}</p>
                  <p className="text-xs text-[#a8aba0] max-w-sm">
                    Upload an original JPEG/PNG fundus capture using the control on the right panel.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* AI DECISION-SUPPORT FINDINGS CARD */}
          {aiRun && (
            <div className="bg-white border border-[#e8e4d8] rounded-2xl p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-[#e8e4d8] pb-2">
                <div className="flex items-center gap-2">
                  <Sparkles size={16} className="text-[#4a5320]" />
                  <h3 className="font-bold text-sm text-[#1c1d1a]">
                    Research AI Screening Output &amp; Explainability
                  </h3>
                  <span className="text-[10px] font-mono text-[#7a7d72] bg-[#f5f3ec] px-2 py-0.5 rounded-full border border-[#e8e4d8]">
                    {aiRun.model_key}
                  </span>
                </div>
                <span
                  className={`text-[10px] font-mono font-semibold px-2.5 py-0.5 rounded-full ${
                    aiRun.overall_status === 'quality_failed'
                      ? 'bg-amber-100 text-amber-900 border border-amber-300'
                      : aiRun.overall_review_required
                      ? 'bg-amber-50 text-amber-900 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                  }`}
                >
                  {aiRun.overall_status.toUpperCase()}
                </span>
              </div>

              {/* Bilateral Summary Banner */}
              <div className="p-3 bg-[#f5f3ec] border border-[#e8e4d8] rounded-xl text-xs text-[#5a5d52] flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[#1c1d1a]">Bilateral Summary:</span>
                  <span>Higher Risk Eye: <strong className="text-[#4a5320]">{aiRun.higher_risk_eye || 'Equal/Bilateral'}</strong></span>
                  <span>•</span>
                  <span>Highest Severity: <strong className="text-[#4a5320]">{aiRun.highest_predicted_label?.replace(/_/g, ' ') || 'None'}</strong></span>
                </div>
                <div className="font-mono text-[10px] text-[#7a7d72]">
                  Model: EfficientNet-B0 (Epoch {aiRun.checkpoint_epoch})
                </div>
              </div>

              {/* AI Automated Clinical Screening Report Card */}
              <div className="bg-[#fcfbf9] border border-[#d8debe] rounded-2xl p-4 sm:p-5 shadow-xs space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#e8e4d8] pb-2.5">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded-lg bg-[#4a5320] text-white">
                      <Sparkles size={16} />
                    </div>
                    <div>
                      <h4 className="font-serif text-sm sm:text-base font-bold text-[#1c1d1a]">
                        AI Automated Clinical Screening Report
                      </h4>
                      <p className="text-[11px] text-[#7a7d72] font-mono">
                        Bilateral Decision Support Synthesis • Generated from EfficientNet-B0 Neural Network
                      </p>
                    </div>
                  </div>
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] self-start sm:self-auto">
                    {aiRun.overall_review_required ? 'Clinical Review Required' : 'Standard Advisory'}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 bg-white rounded-xl border border-[#e8e4d8] space-y-1">
                    <div className="text-[10px] font-mono uppercase text-[#7a7d72] font-semibold">Primary DR Finding</div>
                    <div className="font-serif text-sm font-bold text-[#4a5320]">
                      {aiRun.highest_predicted_grade !== null ? `Grade ${aiRun.highest_predicted_grade} (${aiRun.higher_risk_eye || 'OD'})` : 'Ungraded'}
                    </div>
                    <p className="text-[11px] text-[#5a5d52] leading-relaxed">
                      {aiRun.highest_predicted_grade === 0 && 'No signs of diabetic retinopathy detected in bilateral fundus scans.'}
                      {aiRun.highest_predicted_grade === 1 && 'Mild NPDR features detected with microaneurysms; routine follow-up recommended.'}
                      {aiRun.highest_predicted_grade === 2 && 'Moderate NPDR changes identified; clinical review advised within 2–4 months.'}
                      {aiRun.highest_predicted_grade === 3 && 'Severe NPDR changes identified with elevated risk of progression.'}
                      {aiRun.highest_predicted_grade === 4 && 'Proliferative retinopathy findings flagged; prompt vitreoretinal evaluation advised.'}
                      {aiRun.highest_predicted_grade === null && 'Image quality prevented definitive automated grading.'}
                    </p>
                  </div>

                  <div className="p-3 bg-white rounded-xl border border-[#e8e4d8] space-y-1">
                    <div className="text-[10px] font-mono uppercase text-[#7a7d72] font-semibold">Vision Threat Risk</div>
                    <div className="font-serif text-sm font-bold text-[#1c1d1a]">
                      {aiRun.higher_risk_eye ? `${aiRun.higher_risk_eye} Primary Risk Eye` : 'Bilateral Symmetry'}
                    </div>
                    <p className="text-[11px] text-[#5a5d52] leading-relaxed">
                      {aiRun.overall_review_required
                        ? 'Entropy or VTDR threshold met. Independent specialist sign-off is advised.'
                        : 'Low uncertainty parameters; standard surveillance schedule indicated.'}
                    </p>
                  </div>

                  <div className="p-3 bg-white rounded-xl border border-[#e8e4d8] space-y-1">
                    <div className="text-[10px] font-mono uppercase text-[#7a7d72] font-semibold">Recommended Surveillance</div>
                    <div className="font-serif text-sm font-bold text-[#1c1d1a]">
                      {aiRun.highest_predicted_grade && aiRun.highest_predicted_grade >= 2 ? 'Specialist Referral' : 'Annual Follow-up'}
                    </div>
                    <p className="text-[11px] text-[#5a5d52] leading-relaxed">
                      Grad-CAM visual attention overlays available in viewport above for anatomical verification.
                    </p>
                  </div>
                </div>
              </div>

              {/* Eye Results Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                {aiRun.eye_results.map((eye) => (
                  <div
                    key={eye.id}
                    className={`p-4 rounded-xl border space-y-3 ${
                      eye.gradable
                        ? 'bg-[#faf9f5] border-[#e8e4d8]'
                        : 'bg-amber-50/70 border-amber-200'
                    }`}
                  >
                    <div className="flex items-center justify-between font-bold text-[#1c1d1a]">
                      <span className="font-mono text-sm">{eye.eye === 'OD' ? 'Right Eye (OD)' : 'Left Eye (OS)'}</span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                          eye.gradable ? 'bg-emerald-100 text-emerald-900' : 'bg-rose-100 text-rose-900'
                        }`}
                      >
                        {eye.gradable ? 'Gradable' : 'Ungradable Quality'}
                      </span>
                    </div>

                    {eye.gradable ? (
                      <>
                        <div className="flex items-baseline justify-between border-b border-[#e8e4d8]/70 pb-2">
                          <div className="text-base font-bold font-serif text-[#4a5320]">
                            {eye.predicted_label?.replace(/_/g, ' ') || 'Ungraded'}
                          </div>
                          <div className="text-[11px] font-mono font-semibold text-[#1c1d1a]">
                            Confidence: {((eye.confidence_max_prob || 0) * 100).toFixed(1)}%
                          </div>
                        </div>

                        {/* 5-Class Probability Distribution Bars */}
                        <div className="space-y-1.5 pt-1">
                          <div className="text-[10px] font-mono uppercase text-[#7a7d72] font-semibold">
                            5-Class DR Probability Distribution:
                          </div>
                          {DR_PROB_CLASSES.map((cls) => {
                            const p = extractEyeProb(eye.probabilities, cls.grade);
                            const pct = (p * 100).toFixed(1);
                            const isPredicted = eye.predicted_grade === cls.grade;

                            return (
                              <div key={cls.key} className="space-y-0.5">
                                <div className="flex justify-between text-[10px] font-mono">
                                  <span className={isPredicted ? 'font-bold text-[#1c1d1a] flex items-center gap-1' : 'text-[#7a7d72]'}>
                                    {cls.label}
                                    {isPredicted && <span className="text-[9px] text-[#4a5320] font-semibold">(Predicted)</span>}
                                  </span>
                                  <span className={isPredicted ? 'font-bold text-[#4a5320]' : 'text-[#7a7d72]'}>
                                    {pct}%
                                  </span>
                                </div>
                                <div className="w-full bg-[#e8e4d8] rounded-full h-1.5 overflow-hidden">
                                  <div
                                    className={`${cls.barColor} h-1.5 rounded-full transition-all`}
                                    style={{ width: `${Math.max(Number(pct), 1)}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {/* Clinical Telemetry Readouts */}
                        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-[#7a7d72] bg-[#f2f0e6]/70 p-2.5 rounded-lg border border-[#e8e4d8]">
                          <div>Top-2 Margin: <span className="text-[#1c1d1a] font-semibold">{((eye.top2_margin || 0) * 100).toFixed(1)}%</span></div>
                          <div>Entropy: <span className="text-[#1c1d1a] font-semibold">{eye.normalized_entropy?.toFixed(3) || '—'}</span></div>
                          <div>VTDR Risk: <span className="text-[#1c1d1a] font-semibold">{((eye.vtdr_prob_sum || 0) * 100).toFixed(1)}%</span></div>
                          <div>Review Required: <span className={eye.uncertainty_review_required ? 'text-amber-800 font-bold' : 'text-emerald-800 font-semibold'}>{eye.uncertainty_review_required ? 'YES' : 'NO'}</span></div>
                        </div>

                        {/* Dynamic AI Explainability Narrative */}
                        {eye.explanation?.explanation_text && (
                          <div className="p-3 bg-white rounded-lg border border-[#e8e4d8] text-[11px] text-[#2e3129] leading-relaxed space-y-1">
                            <div className="font-bold font-mono text-[10px] uppercase text-[#4a5320] flex items-center gap-1">
                              <Sparkles size={11} />
                              <span>Clinical Explainability Narrative:</span>
                            </div>
                            <p className="whitespace-pre-line text-[#3f4339]">{eye.explanation.explanation_text}</p>
                          </div>
                        )}

                        {eye.uncertainty_reasons.length > 0 && (
                          <div className="text-[10px] text-amber-800 bg-amber-50 p-2 rounded-lg border border-amber-200">
                            <strong>Review Triggers:</strong> {eye.uncertainty_reasons.join('; ')}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-xs text-rose-800 font-mono space-y-1 p-2 bg-rose-50 rounded-lg border border-rose-200">
                        <div className="font-bold">Model Refused Grade</div>
                        <div>Reason: {eye.quality_reason}</div>
                        <div className="text-[10px] text-rose-600">Grad-CAM explainability is withheld for ungradable captures to protect clinical safety.</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="p-2.5 bg-[#f5f3ec] border border-[#e8e4d8] rounded-xl text-[11px] text-[#5a5d52]">
                <strong>Research Note:</strong> Evaluated in {aiRun.execution_ms}ms with SHA-256 verification ({aiRun.checkpoint_sha256.slice(0, 16)}...). All research inferences require independent clinical sign-off.
              </div>
            </div>
          )}

          {/* DOCTOR CLINICAL REVIEW SIGN-OFF CARD */}
          <div className="bg-white border border-[#e8e4d8] rounded-2xl p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#e8e4d8] pb-2">
              <div className="flex items-center gap-2">
                <UserCheck size={18} className="text-[#4a5320]" />
                <h3 className="font-bold text-sm text-[#1c1d1a]">
                  Qualified Healthcare Professional Sign-Off
                </h3>
              </div>
              {clinicalReview?.is_signed && (
                <span className="text-[11px] font-mono font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300">
                  Signed &amp; Locked
                </span>
              )}
            </div>

            {clinicalReview ? (
              <div className="space-y-3 text-xs bg-[#f2f4e8]/50 p-4 rounded-xl border border-[#d8debe]">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <span className="text-[#7a7d72] font-mono text-[11px] uppercase">Reviewer Credential:</span>
                    <div className="font-bold text-[#1c1d1a]">{clinicalReview.reviewer_name_snapshot}</div>
                    <div className="font-mono text-[#4a5320]">{clinicalReview.reviewer_registration_number_snapshot}</div>
                  </div>
                  <div>
                    <span className="text-[#7a7d72] font-mono text-[11px] uppercase">Confirmed Severity:</span>
                    <div className="font-bold text-[#1c1d1a] text-sm">
                      {clinicalReview.worst_eye_confirmed_label?.replace(/_/g, ' ') || 'Recapture Ordered'}
                    </div>
                    <div className="text-[#7a7d72] text-[11px]">
                      OD: Grade {clinicalReview.od_confirmed_grade ?? '—'} • OS: Grade {clinicalReview.os_confirmed_grade ?? '—'}
                    </div>
                  </div>
                </div>

                <div>
                  <span className="text-[#7a7d72] font-mono text-[11px] uppercase">Clinical Findings:</span>
                  <p className="text-[#1c1d1a] mt-0.5 leading-relaxed bg-white p-2.5 rounded-lg border border-[#d8debe]">
                    {clinicalReview.clinical_findings}
                  </p>
                </div>

                <div>
                  <span className="text-[#7a7d72] font-mono text-[11px] uppercase">Follow-Up Plan:</span>
                  <p className="text-[#1c1d1a] mt-0.5 leading-relaxed bg-white p-2.5 rounded-lg border border-[#d8debe]">
                    {clinicalReview.follow_up_plan}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[#d8debe]">
                  <span className="font-mono text-[11px] text-[#7a7d72]">
                    Signed {new Date(clinicalReview.signed_at).toLocaleString()}
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowReferralModal(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#4a5320] hover:bg-[#3e461a] rounded-full transition-colors cursor-pointer"
                  >
                    <Send size={12} />
                    <span>Dispatch Specialist Referral</span>
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSignClinicalReview} className="space-y-4 text-xs">
                <p className="text-[#5a5d52] leading-relaxed">
                  Qualified eye-care professionals independently inspect retinal findings and provide final diagnostic sign-off. Requires registered medical credential on your account.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                      Right Eye (OD) Confirmed Grade
                    </label>
                    <select
                      value={odGrade}
                      onChange={(e) => setOdGrade(e.target.value === '' ? '' : Number(e.target.value))}
                      className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
                    >
                      <option value="">Select Grade (or ungradable)</option>
                      <option value="0">Grade 0 — No DR</option>
                      <option value="1">Grade 1 — Mild NPDR</option>
                      <option value="2">Grade 2 — Moderate NPDR</option>
                      <option value="3">Grade 3 — Severe NPDR</option>
                      <option value="4">Grade 4 — Proliferative DR</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                      Left Eye (OS) Confirmed Grade
                    </label>
                    <select
                      value={osGrade}
                      onChange={(e) => setOsGrade(e.target.value === '' ? '' : Number(e.target.value))}
                      className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
                    >
                      <option value="">Select Grade (or ungradable)</option>
                      <option value="0">Grade 0 — No DR</option>
                      <option value="1">Grade 1 — Mild NPDR</option>
                      <option value="2">Grade 2 — Moderate NPDR</option>
                      <option value="3">Grade 3 — Severe NPDR</option>
                      <option value="4">Grade 4 — Proliferative DR</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                    AI Advisory Concordance
                  </label>
                  <select
                    value={agreementStatus}
                    onChange={(e) =>
                      setAgreementStatus(
                        e.target.value as 'agreed_with_ai' | 'overrode_ai' | 'independent_no_ai' | 'recapture_ordered'
                      )
                    }
                    className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
                  >
                    <option value="independent_no_ai">Independent Clinical Review</option>
                    <option value="agreed_with_ai">Agreed with AI Advisory</option>
                    <option value="overrode_ai">Overrode AI Advisory</option>
                    <option value="recapture_ordered">Recapture Ordered (Quality Unsuitable)</option>
                  </select>
                </div>

                {agreementStatus === 'overrode_ai' && (
                  <div>
                    <label className="block font-medium text-amber-900 mb-1 font-mono text-[11px]">
                      Clinical Override Rationale *
                    </label>
                    <textarea
                      required
                      rows={2}
                      value={overrideRationale}
                      onChange={(e) => setOverrideRationale(e.target.value)}
                      placeholder="Explain clinical findings that justify diverging from AI advisory..."
                      className="w-full p-2.5 bg-[#faf9f5] border border-amber-300 rounded-xl text-xs text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
                    />
                  </div>
                )}

                <div>
                  <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                    Ophthalmic Findings *
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={findingsText}
                    onChange={(e) => setFindingsText(e.target.value)}
                    placeholder="Document fundus observations, vascular architecture, lesions, or foveal integrity..."
                    className="w-full p-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                    Management &amp; Follow-up Plan *
                  </label>
                  <input
                    type="text"
                    required
                    value={followUpPlan}
                    onChange={(e) => setFollowUpPlan(e.target.value)}
                    placeholder="e.g. Annual screening in 12 months, or tertiary referral within 2 weeks"
                    className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="recaptureCheck"
                    checked={recaptureRequired}
                    onChange={(e) => setRecaptureRequired(e.target.checked)}
                    className="rounded border-[#e8e4d8] text-[#4a5320] focus:ring-[#4a5320]"
                  />
                  <label htmlFor="recaptureCheck" className="text-xs text-[#5a5d52]">
                    Mark encounter as requiring image recapture due to media opacity or acquisition artifact
                  </label>
                </div>

                <div className="p-3 bg-[#f2f4e8] border border-[#d8debe] rounded-xl flex items-start gap-2.5">
                  <input
                    type="checkbox"
                    id="confirmCheck"
                    required
                    checked={confirmIndependent}
                    onChange={(e) => setConfirmIndependent(e.target.checked)}
                    className="rounded border-[#d8debe] text-[#4a5320] focus:ring-[#4a5320] mt-0.5 shrink-0"
                  />
                  <label htmlFor="confirmCheck" className="text-xs text-[#4a5320] leading-relaxed">
                    <strong>Practitioner Attestation:</strong> I confirm that I have independently reviewed the bilateral fundus images and accept clinical accountability for these findings.
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={isSigningReview || !confirmIndependent}
                  className={`w-full py-2.5 px-4 rounded-full text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                    confirmIndependent && !isSigningReview
                      ? 'bg-[#4a5320] hover:bg-[#3e461a] text-white cursor-pointer shadow-xs'
                      : 'bg-[#edeae0] text-[#a8aba0] cursor-not-allowed'
                  }`}
                >
                  {isSigningReview ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span>Signing Assessment...</span>
                    </>
                  ) : (
                    <>
                      <FileCheck size={14} />
                      <span>Sign Independent Clinical Assessment</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* RIGHT CONTROL SIDEBAR (4 cols) */}
        <div className="lg:col-span-5 xl:col-span-4 space-y-4">
          <div className="bg-white border border-[#e8e4d8] rounded-2xl p-5 shadow-xs space-y-4">
            <h3 className="font-serif text-base text-[#1c1d1a] border-b border-[#e8e4d8] pb-2">
              Retinal Scan Management
            </h3>

            {/* Eye Laterality Switch */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#1c1d1a]">Select Eye</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setActiveEye('OD')}
                  className={`p-2.5 rounded-xl border text-xs font-mono text-center transition-all cursor-pointer ${
                    activeEye === 'OD'
                      ? 'bg-[#f2f4e8] text-[#4a5320] border-[#4a5320] font-bold shadow-2xs'
                      : 'bg-[#faf9f5] text-[#5a5d52] border-[#e8e4d8] hover:bg-[#f5f3ec]'
                  }`}
                >
                  OD (Right Eye)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveEye('OS')}
                  className={`p-2.5 rounded-xl border text-xs font-mono text-center transition-all cursor-pointer ${
                    activeEye === 'OS'
                      ? 'bg-[#f2f4e8] text-[#4a5320] border-[#4a5320] font-bold shadow-2xs'
                      : 'bg-[#faf9f5] text-[#5a5d52] border-[#e8e4d8] hover:bg-[#f5f3ec]'
                  }`}
                >
                  OS (Left Eye)
                </button>
              </div>
            </div>

            {/* Upload or Controlled Replace Button */}
            <div className="space-y-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png"
                onChange={handleUploadOrReplace}
                className="hidden"
              />

              <button
                type="button"
                disabled={!canModifyImages || uploadProgress !== null}
                onClick={() => fileInputRef.current?.click()}
                className={`w-full py-2.5 px-4 rounded-full text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                  canModifyImages
                    ? 'bg-[#4a5320] hover:bg-[#3e461a] text-white cursor-pointer shadow-xs'
                    : 'bg-[#edeae0] text-[#a8aba0] cursor-not-allowed'
                }`}
              >
                {uploadProgress !== null ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Uploading ({uploadProgress}%)</span>
                  </>
                ) : currentEyeData ? (
                  <>
                    <Replace size={14} />
                    <span>Replace {activeEye} Scan</span>
                  </>
                ) : (
                  <>
                    <UploadCloud size={14} />
                    <span>Upload {activeEye} Scan</span>
                  </>
                )}
              </button>
            </div>

            {/* Scan Summary Card */}
            <div className="p-3 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs space-y-1.5 font-mono">
              <div className="font-semibold text-[#4a5320] uppercase text-[11px] mb-1">
                {activeEye} Scan Details
              </div>
              {currentEyeData ? (
                <div className="space-y-1 text-[11px]">
                  <div className="flex justify-between gap-2">
                    <span className="text-[#7a7d72]">Image Format:</span>
                    <span className="text-[#1c1d1a] uppercase">{currentEyeData.file_extension}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-[#7a7d72]">File Size:</span>
                    <span className="text-[#1c1d1a]">{formatBytes(currentEyeData.file_size_bytes)}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-[#7a7d72]">Resolution:</span>
                    <span className="text-[#1c1d1a]">{currentEyeData.image_width} × {currentEyeData.image_height} px</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-[#7a7d72]">Storage Status:</span>
                    <span className="text-emerald-700 font-medium">Encrypted & Stored</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[#7a7d72]">No image stored for {activeEye} yet.</p>
              )}
            </div>

            {/* Run AI Screening Trigger */}
            <div className="pt-2 border-t border-[#e8e4d8] space-y-2">
              <div className="text-xs font-semibold text-[#1c1d1a] flex items-center gap-1.5">
                <Sparkles size={14} className="text-[#4a5320]" />
                <span>AI Screening Analysis</span>
              </div>
              <p className="text-[11px] text-[#7a7d72] leading-relaxed">
                Applies Phase 11 hardened optical quality gates and preserved research checkpoints (E2 sampler default).
              </p>

              <button
                type="button"
                disabled={!canRunAi || isRunningAi}
                onClick={handleRunAiAnalysis}
                className={`w-full py-2.5 px-4 rounded-full text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                  canRunAi && !isRunningAi
                    ? 'bg-[#6f7d3e] hover:bg-[#5a6730] text-white cursor-pointer shadow-xs'
                    : 'bg-[#edeae0] text-[#a8aba0] cursor-not-allowed'
                }`}
              >
                {isRunningAi ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Evaluating Retinal Images...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    <span>{aiRun ? 'Re-run AI Advisory Analysis' : 'Run Quality-Gated AI Analysis'}</span>
                  </>
                )}
              </button>
            </div>

            {/* Submit Screening for QA */}
            {screening.status === 'draft' && (
              <div className="pt-2 border-t border-[#e8e4d8]">
                <button
                  type="button"
                  disabled={!canSubmitForQA || isSubmitting}
                  onClick={handleSubmitScreening}
                  className={`w-full py-2.5 px-4 rounded-full text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                    canSubmitForQA && !isSubmitting
                      ? 'bg-[#4a5320] hover:bg-[#3e461a] text-white cursor-pointer shadow-xs'
                      : 'bg-[#edeae0] text-[#a8aba0] cursor-not-allowed'
                  }`}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <span>Submit for Quality Assessment</span>
                      <ArrowRight size={14} />
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. LONGITUDINAL COMPARISON SECTION */}
      {showComparison && screening.patient_id && (
        <div className="pt-2">
          <ScreeningComparisonViewer
            currentScreeningId={screening.id}
            patientId={screening.patient_id}
          />
        </div>
      )}

      {/* DISPATCH REFERRAL MODAL */}
      {showReferralModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#e8e4d8] rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#e8e4d8] pb-3">
              <h3 className="font-serif text-lg font-bold text-[#1c1d1a] flex items-center gap-2">
                <Send size={18} className="text-[#4a5320]" />
                <span>Dispatch Specialist Referral</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowReferralModal(false)}
                className="text-[#7a7d72] hover:text-[#1c1d1a] text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateReferral} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                  Clinical Urgency
                </label>
                <select
                  value={refUrgency}
                  onChange={(e) =>
                    setRefUrgency(
                      e.target.value as 'IMMEDIATE_48H' | 'WITHIN_2_WEEKS' | 'STANDARD_SURVEILLANCE'
                    )
                  }
                  className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a]"
                >
                  <option value="IMMEDIATE_48H">Immediate (within 48 Hours) — High Risk / PDR</option>
                  <option value="WITHIN_2_WEEKS">Within 2 Weeks — Moderate to Severe NPDR / DME</option>
                  <option value="STANDARD_SURVEILLANCE">Standard Surveillance (Annual Follow-up)</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                  Target Facility
                </label>
                <input
                  type="text"
                  required
                  value={refFacility}
                  onChange={(e) => setRefFacility(e.target.value)}
                  className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a]"
                />
              </div>

              <div>
                <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                  Target Specialty
                </label>
                <input
                  type="text"
                  required
                  value={refSpecialty}
                  onChange={(e) => setRefSpecialty(e.target.value)}
                  className="w-full p-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a]"
                />
              </div>

              <div>
                <label className="block font-medium text-[#1c1d1a] mb-1 font-mono text-[11px]">
                  Referral Indication &amp; Reason Summary *
                </label>
                <textarea
                  required
                  rows={3}
                  value={refReason}
                  onChange={(e) => setRefReason(e.target.value)}
                  placeholder="Summarize reasons for specialist referral (e.g., macular edema, high-risk proliferative changes)..."
                  className="w-full p-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReferralModal(false)}
                  className="px-4 py-2 rounded-full border border-[#e8e4d8] text-xs font-medium text-[#5a5d52] hover:bg-[#faf9f5]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingReferral}
                  className="px-5 py-2 rounded-full text-xs font-semibold text-white bg-[#4a5320] hover:bg-[#3e461a] transition-all cursor-pointer shadow-xs"
                >
                  {isCreatingReferral ? 'Dispatching...' : 'Confirm & Dispatch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
