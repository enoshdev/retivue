'use client';

import React, { useState, useRef, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useClinical } from '@/context/ClinicalContext';
import { ApiScreening, ApiScreeningImage, screeningApi } from '@/lib/api';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import { CdsDisclaimerBanner } from '@/components/clinical/CdsDisclaimerBanner';
import { PageHeader } from '@/components/layout/PageHeader';
import { SecureFundusImage } from '@/components/clinical/SecureFundusImage';
import {
  UploadCloud,
  AlertTriangle,
  X,
  ArrowRight,
  RefreshCw,
  Info,
  CheckCircle2,
  ShieldCheck,
  Loader2,
  Replace,
  FilePlus2,
} from 'lucide-react';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function NewScreeningContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialPatientParam = searchParams.get('patientId') || '';
  const existingScreeningParam = searchParams.get('screeningId') || '';

  const {
    patients,
    patientsLoading,
    currentUser,
    createScreening,
    fetchScreeningById,
    upsertScreeningInCache,
    refreshPatients,
    setNotification,
  } = useClinical();

  const [selectedPatientId, setSelectedPatientId] = useState<string>(initialPatientParam);
  const [cameraModel, setCameraModel] = useState<string>('Topcon TRC-NW400 (45° Non-Mydriatic)');
  const [clinicalNotes, setClinicalNotes] = useState<string>('');

  const [activeScreening, setActiveScreening] = useState<ApiScreening | null>(null);
  const [initializingScreening, setInitializingScreening] = useState<boolean>(false);

  // Per-eye upload progress & error state
  const [odProgress, setOdProgress] = useState<number | null>(null);
  const [osProgress, setOsProgress] = useState<number | null>(null);
  const [odError, setOdError] = useState<string | null>(null);
  const [osError, setOsError] = useState<string | null>(null);

  const [globalError, setGlobalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const odInputRef = useRef<HTMLInputElement>(null);
  const osInputRef = useRef<HTMLInputElement>(null);
  const odReplaceInputRef = useRef<HTMLInputElement>(null);
  const osReplaceInputRef = useRef<HTMLInputElement>(null);

  // Load existing screening if screeningId query param is provided (resuming draft/incomplete)
  useEffect(() => {
    let active = true;
    if (existingScreeningParam) {
      fetchScreeningById(existingScreeningParam).then((loaded) => {
        if (active && loaded) {
          setActiveScreening(loaded);
          setSelectedPatientId(loaded.patient_id);
          if (loaded.camera_model) setCameraModel(loaded.camera_model);
          if (loaded.clinical_notes) setClinicalNotes(loaded.clinical_notes);
        }
      });
    }
    return () => {
      active = false;
    };
  }, [existingScreeningParam, fetchScreeningById]);

  const effectivePatientId = activeScreening?.patient_id || selectedPatientId || patients[0]?.id || '';
  const selectedPatient = patients.find((p) => p.id === effectivePatientId);

  const ensureScreeningCreated = async (): Promise<ApiScreening | null> => {
    if (activeScreening) return activeScreening;
    if (!effectivePatientId) {
      setGlobalError('Please select a registered patient before initializing a screening encounter.');
      return null;
    }

    setInitializingScreening(true);
    setGlobalError(null);
    try {
      const created = await createScreening({
        patient_id: effectivePatientId,
        camera_model: cameraModel,
        clinical_notes: clinicalNotes.trim() || undefined,
      });
      setActiveScreening(created);
      return created;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create screening encounter.';
      setGlobalError(msg);
      return null;
    } finally {
      setInitializingScreening(false);
    }
  };

  const handleEyeFileChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
    eye: 'OD' | 'OS',
    isReplace: boolean
  ) => {
    const file = e.target.files?.[0];
    // Reset input so re-selecting the same file later still triggers onChange
    e.target.value = '';
    if (!file) return;

    if (eye === 'OD') {
      setOdError(null);
    } else {
      setOsError(null);
    }
    setGlobalError(null);

    const screening = await ensureScreeningCreated();
    if (!screening) return;

    const setProgress = eye === 'OD' ? setOdProgress : setOsProgress;
    const setEyeErr = eye === 'OD' ? setOdError : setOsError;

    setProgress(0);
    try {
      if (isReplace) {
        await screeningApi.replaceImage(screening.id, eye, file, (pct) => setProgress(pct));
      } else {
        await screeningApi.uploadImage(screening.id, eye, file, (pct) => setProgress(pct));
      }

      // Reload latest authoritative screening state from PostgreSQL
      const updated = await screeningApi.get(screening.id);
      setActiveScreening(updated);
      upsertScreeningInCache(updated);
      setNotification({
        type: 'success',
        message: `${eye} retinal image validated and stored privately (${updated.screening_reference}).`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `Failed to upload ${eye} image.`;
      setEyeErr(msg);
    } finally {
      setProgress(null);
    }
  };

  const handleSubmitForQualityAssessment = async () => {
    if (!activeScreening) return;
    setGlobalError(null);
    setIsSubmitting(true);
    try {
      const submitted = await screeningApi.submit(activeScreening.id);
      setActiveScreening(submitted);
      upsertScreeningInCache(submitted);
      await refreshPatients();
      setNotification({
        type: 'success',
        message: `Screening ${submitted.screening_reference} submitted and ready for quality assessment.`,
      });
      router.push(`/app/screenings/${submitted.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to submit screening for quality assessment.';
      setGlobalError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const odImage: ApiScreeningImage | null | undefined = activeScreening?.od_image;
  const osImage: ApiScreeningImage | null | undefined = activeScreening?.os_image;
  const hasOd = Boolean(odImage);
  const hasOs = Boolean(osImage);
  const isBilateral = hasOd && hasOs;
  const hasOnlyOneEye = (hasOd || hasOs) && !isBilateral;

  const patientConsentGranted = Boolean(selectedPatient?.consentGiven);
  const patientConsentLabel = selectedPatient?.consentStatus || 'missing';
  const canSubmit =
    Boolean(activeScreening) &&
    isBilateral &&
    patientConsentGranted &&
    odProgress === null &&
    osProgress === null &&
    !isSubmitting;

  return (
    <div className="space-y-6 pb-16 max-w-5xl mx-auto select-none">
      {/* Top Header */}
      <PageHeader
        backHref="/app/screenings"
        backLabel="Back to History"
        eyebrow="BILATERAL RETINAL IMAGE INGESTION"
        title={activeScreening ? `Screening ${activeScreening.screening_reference}` : 'New Retinal Screening'}
        subtitle="Create a verified patient screening encounter, upload unmodified JPEG or PNG fundus images, and verify consent prior to submission"
        actions={
          <div className="text-right hidden sm:block">
            <span className="text-[10px] font-mono text-[#7a7d72] block uppercase">
              AUTHENTICATED CLINICIAN
            </span>
            <span className="text-xs font-semibold text-[#1c1d1a] font-mono">
              {currentUser.name}
            </span>
          </div>
        }
      />

      <CdsDisclaimerBanner compact />

      {/* Global Backend Error Alert */}
      {globalError && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-rose-600 shrink-0" />
            <span>{globalError}</span>
          </div>
          <button
            type="button"
            onClick={() => setGlobalError(null)}
            className="text-rose-600 hover:text-rose-900 cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Step 1: Patient & Equipment Selection */}
      <div className="p-5 sm:p-6 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#e8e4d8]">
          <div className="flex items-center gap-2.5">
            <h2 className="font-serif text-lg text-[#1c1d1a]">
              1. Patient & Acquisition Setup
            </h2>
            {activeScreening && <StatusBadge type="status" value={activeScreening.status} size="sm" />}
          </div>
          <Link
            href="/app/patients/new"
            className="text-xs text-[#4a5320] hover:underline font-semibold no-underline"
          >
            + Register New Patient
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-[#1c1d1a] mb-1.5">
              Select Owned Patient Beneficiary
            </label>
            {patientsLoading && patients.length === 0 ? (
              <div className="flex items-center gap-2 text-xs text-[#7a7d72] p-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl">
                <Loader2 size={14} className="animate-spin text-[#4a5320]" />
                <span>Loading owned patients from PostgreSQL...</span>
              </div>
            ) : patients.length > 0 ? (
              <select
                value={effectivePatientId}
                disabled={Boolean(activeScreening)}
                onChange={(e) => setSelectedPatientId(e.target.value)}
                className="w-full text-xs bg-[#faf9f5] border border-[#e8e4d8] rounded-xl p-2.5 text-[#1c1d1a] focus:outline-none focus:border-[#4a5320] font-sans transition-colors disabled:opacity-70"
              >
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.fullName} ({p.mrn}) • {p.age}y {p.gender} • {p.diabetesType}
                  </option>
                ))}
              </select>
            ) : (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-2">
                <p>No active patients found in your account registry.</p>
                <Link
                  href="/app/patients/new"
                  className="inline-flex items-center gap-1.5 font-semibold text-[#4a5320] underline"
                >
                  Register a patient in PostgreSQL first →
                </Link>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#1c1d1a] mb-1.5">
              Fundus Camera Modality
            </label>
            <select
              value={cameraModel}
              disabled={Boolean(activeScreening)}
              onChange={(e) => setCameraModel(e.target.value)}
              className="w-full text-xs bg-[#faf9f5] border border-[#e8e4d8] rounded-xl p-2.5 text-[#1c1d1a] focus:outline-none focus:border-[#4a5320] font-sans transition-colors disabled:opacity-70"
            >
              <option value="Topcon TRC-NW400 (45° Non-Mydriatic)">
                Topcon TRC-NW400 (45° Non-Mydriatic)
              </option>
              <option value="Remidio NM-FOP Handheld (45° Tele-Van)">
                Remidio NM-FOP Handheld (45° Tele-Van)
              </option>
              <option value="Canon CR-2 AF Digital Non-Mydriatic">
                Canon CR-2 AF Digital Non-Mydriatic
              </option>
              <option value="Zeiss Visucam 500 Clinical Workstation">
                Zeiss Visucam 500 Clinical Workstation
              </option>
            </select>
          </div>
        </div>

        {/* Optional Clinical Intake Notes + Explicit Encounter Initialization */}
        {!activeScreening && patients.length > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 pt-1">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-[#1c1d1a] mb-1">
                Encounter Notes (Optional)
              </label>
              <input
                type="text"
                value={clinicalNotes}
                onChange={(e) => setClinicalNotes(e.target.value)}
                placeholder="e.g. Pupil dilation status, ocular media observations..."
                className="w-full text-xs bg-[#faf9f5] border border-[#e8e4d8] rounded-xl px-3 py-2 text-[#1c1d1a] focus:outline-none focus:border-[#4a5320]"
              />
            </div>
            <button
              type="button"
              disabled={!effectivePatientId || initializingScreening}
              onClick={ensureScreeningCreated}
              className="inline-flex items-center gap-1.5 bg-[#f2f4e8] hover:bg-[#e7edd3] text-[#4a5320] border border-[#d8debe] px-4 py-2 rounded-full text-xs font-semibold transition-colors cursor-pointer shrink-0 disabled:opacity-50"
            >
              {initializingScreening ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FilePlus2 size={14} />
              )}
              <span>Initialize Screening Record</span>
            </button>
          </div>
        )}

        {/* Consent Verification Banner */}
        {selectedPatient && (
          <div
            className={`p-3.5 rounded-xl border text-xs flex flex-wrap items-center justify-between gap-3 ${
              patientConsentGranted
                ? 'bg-[#f2f4e8] border-[#d8debe] text-[#4a5320]'
                : 'bg-rose-50 border-rose-200 text-rose-900'
            }`}
          >
            <div className="flex items-center gap-2">
              {patientConsentGranted ? (
                <ShieldCheck size={16} className="text-[#4a5320] shrink-0" />
              ) : (
                <AlertTriangle size={16} className="text-rose-600 shrink-0" />
              )}
              <span>
                {patientConsentGranted ? (
                  <>
                    <strong>Informed Consent Verified</strong> ({selectedPatient.consentDate}) — Ready for bilateral acquisition and quality assessment submission.
                  </>
                ) : (
                  <>
                    <strong>Consent Required for Processing ({patientConsentLabel}):</strong> Draft upload is allowed, but screening submission is blocked until informed retinal screening consent is granted.
                  </>
                )}
              </span>
            </div>
            {!patientConsentGranted && (
              <Link
                href={`/app/patients/${selectedPatient.id}`}
                className="text-xs font-semibold text-rose-800 underline hover:text-rose-950"
              >
                Manage Patient Consent →
              </Link>
            )}
          </div>
        )}
      </div>

      {/* Step 2: Dual-Eye Acquisition Dropzones */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-serif text-lg text-[#1c1d1a]">
            2. Dual-Eye Retinal Photographs
          </h2>
          <span className="text-xs text-[#7a7d72] font-mono">
            Supported Formats: JPEG, PNG Only • Max 20 MB • Originals Preserved Losslessly
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* OD (Right Eye) Acquisition Box */}
          <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#e8e4d8]">
              <div className="flex items-center gap-2 font-semibold text-xs text-[#1c1d1a]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#4a5320]" />
                <span>Right Eye (OD)</span>
              </div>
              {odImage && activeScreening && activeScreening.status !== 'cancelled' && (
                <>
                  <button
                    type="button"
                    disabled={odProgress !== null}
                    onClick={() => odReplaceInputRef.current?.click()}
                    className="text-xs text-[#4a5320] hover:text-[#3e461a] flex items-center gap-1 cursor-pointer font-semibold disabled:opacity-50"
                  >
                    <Replace size={13} />
                    <span>Replace Image</span>
                  </button>
                  <input
                    ref={odReplaceInputRef}
                    type="file"
                    accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                    className="hidden"
                    onChange={(e) => handleEyeFileChange(e, 'OD', true)}
                  />
                </>
              )}
            </div>

            {odError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-[11px] text-rose-800 flex items-start gap-2">
                <AlertTriangle size={14} className="text-rose-600 shrink-0 mt-0.5" />
                <span>{odError}</span>
              </div>
            )}

            {odProgress !== null && (
              <div className="p-4 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-[#4a5320]">
                  <span>Uploading & validating OD original...</span>
                  <span>{odProgress}%</span>
                </div>
                <div className="w-full h-2 bg-[#edebe1] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#4a5320] transition-all duration-150"
                    style={{ width: `${odProgress}%` }}
                  />
                </div>
              </div>
            )}

            {odImage && activeScreening ? (
              <div className="space-y-3">
                <div className="relative aspect-square max-h-56 mx-auto bg-[#0b0c0a] border border-[#262822] rounded-xl overflow-hidden flex items-center justify-center">
                  <SecureFundusImage
                    screeningId={activeScreening.id}
                    eye="OD"
                    versionKey={odImage.id}
                    alt="Right Eye (OD) Retinal Fundus"
                  />
                  <div className="absolute top-2 left-2 px-2.5 py-0.5 bg-black/80 text-white text-[10px] font-mono rounded-full border border-white/10">
                    OD • {odImage.image_width}×{odImage.image_height}
                  </div>
                </div>

                <div className="p-3 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl space-y-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#1c1d1a] text-xs font-mono truncate">
                      {odImage.original_filename || 'OD_Fundus'}
                    </span>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] text-[10px] font-mono shrink-0">
                      <CheckCircle2 size={11} />
                      Stored Privately
                    </span>
                  </div>
                  <div className="text-[11px] text-[#5a5d52] font-mono flex flex-wrap gap-x-3 gap-y-0.5">
                    <span>{odImage.detected_media_type}</span>
                    <span>•</span>
                    <span>{formatBytes(odImage.file_size_bytes)}</span>
                    <span>•</span>
                    <span>SHA256: {odImage.sha256_checksum.slice(0, 12)}…</span>
                  </div>
                  <p className="text-[10px] text-[#7a7d72]">
                    Technical validation passed. Clinical quality assessment awaits Phase 6.
                  </p>
                </div>
              </div>
            ) : (
              <div
                onClick={() => {
                  if (patients.length > 0 && odProgress === null) odInputRef.current?.click();
                }}
                className={`border-2 border-dashed rounded-2xl p-8 text-center transition-colors space-y-2 bg-[#faf9f5] ${
                  patients.length > 0 && odProgress === null
                    ? 'border-[#d8debe] hover:border-[#4a5320] cursor-pointer'
                    : 'border-[#e8e4d8] opacity-60 cursor-not-allowed'
                }`}
              >
                <div className="w-10 h-10 rounded-full bg-[#f2f4e8] mx-auto flex items-center justify-center text-[#4a5320]">
                  <UploadCloud size={20} />
                </div>
                <div className="text-xs font-semibold text-[#1c1d1a]">
                  Select OD (Right Eye) Retinal Image
                </div>
                <p className="text-[11px] text-[#7a7d72]">
                  JPEG (.jpg, .jpeg) or PNG (.png) • Max 20 MB
                </p>
                <input
                  ref={odInputRef}
                  type="file"
                  accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={(e) => handleEyeFileChange(e, 'OD', false)}
                />
              </div>
            )}
          </div>

          {/* OS (Left Eye) Acquisition Box */}
          <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#e8e4d8]">
              <div className="flex items-center gap-2 font-semibold text-xs text-[#1c1d1a]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#6f7d3e]" />
                <span>Left Eye (OS)</span>
              </div>
              {osImage && activeScreening && activeScreening.status !== 'cancelled' && (
                <>
                  <button
                    type="button"
                    disabled={osProgress !== null}
                    onClick={() => osReplaceInputRef.current?.click()}
                    className="text-xs text-[#4a5320] hover:text-[#3e461a] flex items-center gap-1 cursor-pointer font-semibold disabled:opacity-50"
                  >
                    <Replace size={13} />
                    <span>Replace Image</span>
                  </button>
                  <input
                    ref={osReplaceInputRef}
                    type="file"
                    accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                    className="hidden"
                    onChange={(e) => handleEyeFileChange(e, 'OS', true)}
                  />
                </>
              )}
            </div>

            {osError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-[11px] text-rose-800 flex items-start gap-2">
                <AlertTriangle size={14} className="text-rose-600 shrink-0 mt-0.5" />
                <span>{osError}</span>
              </div>
            )}

            {osProgress !== null && (
              <div className="p-4 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-[#4a5320]">
                  <span>Uploading & validating OS original...</span>
                  <span>{osProgress}%</span>
                </div>
                <div className="w-full h-2 bg-[#edebe1] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#4a5320] transition-all duration-150"
                    style={{ width: `${osProgress}%` }}
                  />
                </div>
              </div>
            )}

            {osImage && activeScreening ? (
              <div className="space-y-3">
                <div className="relative aspect-square max-h-56 mx-auto bg-[#0b0c0a] border border-[#262822] rounded-xl overflow-hidden flex items-center justify-center">
                  <SecureFundusImage
                    screeningId={activeScreening.id}
                    eye="OS"
                    versionKey={osImage.id}
                    alt="Left Eye (OS) Retinal Fundus"
                  />
                  <div className="absolute top-2 left-2 px-2.5 py-0.5 bg-black/80 text-white text-[10px] font-mono rounded-full border border-white/10">
                    OS • {osImage.image_width}×{osImage.image_height}
                  </div>
                </div>

                <div className="p-3 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl space-y-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#1c1d1a] text-xs font-mono truncate">
                      {osImage.original_filename || 'OS_Fundus'}
                    </span>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] text-[10px] font-mono shrink-0">
                      <CheckCircle2 size={11} />
                      Stored Privately
                    </span>
                  </div>
                  <div className="text-[11px] text-[#5a5d52] font-mono flex flex-wrap gap-x-3 gap-y-0.5">
                    <span>{osImage.detected_media_type}</span>
                    <span>•</span>
                    <span>{formatBytes(osImage.file_size_bytes)}</span>
                    <span>•</span>
                    <span>SHA256: {osImage.sha256_checksum.slice(0, 12)}…</span>
                  </div>
                  <p className="text-[10px] text-[#7a7d72]">
                    Technical validation passed. Clinical quality assessment awaits Phase 6.
                  </p>
                </div>
              </div>
            ) : (
              <div
                onClick={() => {
                  if (patients.length > 0 && osProgress === null) osInputRef.current?.click();
                }}
                className={`border-2 border-dashed rounded-2xl p-8 text-center transition-colors space-y-2 bg-[#faf9f5] ${
                  patients.length > 0 && osProgress === null
                    ? 'border-[#d8debe] hover:border-[#4a5320] cursor-pointer'
                    : 'border-[#e8e4d8] opacity-60 cursor-not-allowed'
                }`}
              >
                <div className="w-10 h-10 rounded-full bg-[#f2f4e8] mx-auto flex items-center justify-center text-[#4a5320]">
                  <UploadCloud size={20} />
                </div>
                <div className="text-xs font-semibold text-[#1c1d1a]">
                  Select OS (Left Eye) Retinal Image
                </div>
                <p className="text-[11px] text-[#7a7d72]">
                  JPEG (.jpg, .jpeg) or PNG (.png) • Max 20 MB
                </p>
                <input
                  ref={osInputRef}
                  type="file"
                  accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={(e) => handleEyeFileChange(e, 'OS', false)}
                />
              </div>
            )}
          </div>
        </div>

        {/* Missing-Eye Warning */}
        {hasOnlyOneEye && (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-xs flex items-start gap-2.5 text-amber-900">
            <Info size={16} className="text-amber-700 shrink-0 mt-0.5" />
            <p className="leading-relaxed text-xs">
              <strong>Missing-Eye Warning ({!hasOd ? 'Right Eye OD' : 'Left Eye OS'} Missing):</strong> Bilateral screening submission requires both OD and OS fundus photographs. Your uploaded image is saved safely in draft state; upload the remaining eye when ready or save draft to return later.
            </p>
          </div>
        )}
      </div>

      {/* Submission Footer Actions */}
      <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="text-xs text-[#7a7d72] font-mono">
          {!activeScreening
            ? 'Select patient and upload OD/OS images to begin.'
            : isBilateral
            ? patientConsentGranted
              ? 'Bilateral OD + OS stored & consent verified — ready to submit.'
              : 'Bilateral OD + OS stored — patient consent required before submission.'
            : hasOnlyOneEye
            ? 'Incomplete bilateral draft (1 of 2 eye images stored).'
            : 'Draft initialized — awaiting retinal image uploads.'}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {activeScreening ? (
            <Link
              href={`/app/screenings/${activeScreening.id}`}
              className="px-5 py-2.5 border border-[#e8e4d8] text-[#1c1d1a] hover:bg-[#f5f3ec] rounded-full text-xs font-medium no-underline transition-colors"
            >
              Open Draft Workspace
            </Link>
          ) : (
            <Link
              href="/app/screenings"
              className="px-5 py-2.5 border border-[#e8e4d8] text-[#1c1d1a] hover:bg-[#f5f3ec] rounded-full text-xs font-medium no-underline transition-colors"
            >
              Cancel
            </Link>
          )}

          <button
            type="button"
            disabled={!canSubmit}
            onClick={handleSubmitForQualityAssessment}
            className={`inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs ${
              canSubmit
                ? 'bg-[#4a5320] hover:bg-[#3e461a] text-white cursor-pointer'
                : 'bg-[#edeae0] text-[#a8aba0] cursor-not-allowed'
            }`}
          >
            {isSubmitting ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
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
      </div>
    </div>
  );
}

export default function NewScreeningPage() {
  return (
    <Suspense
      fallback={
        <div className="p-12 text-center text-xs text-[#7a7d72] flex items-center justify-center gap-2">
          <Loader2 size={18} className="animate-spin text-[#4a5320]" />
          <span>Loading screening acquisition console...</span>
        </div>
      }
    >
      <NewScreeningContent />
    </Suspense>
  );
}
