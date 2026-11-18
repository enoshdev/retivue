'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useClinical } from '@/context/ClinicalContext';
import { patientApi } from '@/lib/api';
import { PageHeader } from '@/components/layout/PageHeader';
import { PatientTimeline } from '@/components/clinical/PatientTimeline';
import { ScreeningComparisonViewer } from '@/components/clinical/ScreeningComparisonViewer';
import {
  ArrowLeft,
  PlusCircle,
  CheckCircle2,
  Activity,
  FileText,
  User,
  Archive,
  Loader2,
  AlertTriangle,
  ShieldAlert,
  X,
  GitCompare,
} from 'lucide-react';

export default function PatientProfilePage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params?.id as string;
  const { getPatientById, fetchPatientById, archivePatient, setNotification } = useClinical();

  const [patient, setPatient] = useState(getPatientById(patientId));
  const [isLoading, setIsLoading] = useState(!patient);
  const [isArchiving, setIsArchiving] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [updatingConsent, setUpdatingConsent] = useState(false);
  const [compareModalScreeningId, setCompareModalScreeningId] = useState<string | null>(null);

  // Fetch patient record if not in cache
  useEffect(() => {
    let isMounted = true;
    async function load() {
      if (!patient) {
        const record = await fetchPatientById(patientId);
        if (isMounted) {
          setPatient(record || undefined);
          setIsLoading(false);
        }
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [patientId, patient, fetchPatientById]);

  const handleConsentChange = async (grant: boolean) => {
    if (!patient) return;
    setUpdatingConsent(true);
    try {
      if (grant) {
        await patientApi.recordConsent(patient.id, {
          consent_type: 'retinal_screening',
          consent_status: 'granted',
          capture_method: 'digital_acknowledgement',
          notes: 'Informed retinal screening consent recorded from Patient Profile.',
        });
      } else {
        await patientApi.revokeConsent(patient.id, 'Informed consent revoked from Patient Profile.');
      }
      const refreshed = await fetchPatientById(patient.id);
      if (refreshed) setPatient(refreshed);
      setNotification({
        type: grant ? 'success' : 'info',
        message: grant
          ? 'Informed retinal screening consent recorded as granted.'
          : 'Informed retinal screening consent revoked.',
      });
    } catch (err: unknown) {
      setNotification({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to update consent record.',
      });
    } finally {
      setUpdatingConsent(false);
    }
  };

  const handleArchive = async () => {
    setIsArchiving(true);
    try {
      await archivePatient(patientId);
      router.push('/app/patients');
    } catch (err) {
      console.error('Failed to archive patient:', err);
      setIsArchiving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-16 text-center text-xs text-[#7a7d72] flex flex-col items-center justify-center gap-3">
        <Loader2 size={24} className="animate-spin text-[#4a5320]" />
        <span>Loading patient record from PostgreSQL database...</span>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="p-12 text-center bg-white border border-[#e8e4d8] rounded-2xl max-w-lg mx-auto my-12 shadow-xs">
        <AlertTriangle size={28} className="text-amber-600 mx-auto mb-3" />
        <h2 className="text-base font-bold text-[#1c1d1a] font-serif mb-1">Patient Record Not Found</h2>
        <p className="text-xs text-[#7a7d72] mb-5 leading-relaxed">
          No clinical record found matching beneficiary identifier <span className="font-mono">{patientId}</span>. Record may belong to another account or does not exist.
        </p>
        <Link
          href="/app/patients"
          className="inline-flex items-center gap-1.5 bg-[#4a5320] text-white text-xs font-semibold px-4 py-2 rounded-full no-underline hover:bg-[#3e461a] transition-colors"
        >
          <ArrowLeft size={13} />
          <span>Return to Directory</span>
        </Link>
      </div>
    );
  }

  const getInitials = (name: string) => {
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <div className="space-y-6 pb-16 select-none max-w-5xl mx-auto">
      {/* Top Header */}
      <PageHeader
        backHref="/app/patients"
        backLabel="Back to Patients"
        eyebrow={`BENEFICIARY PROFILE • ${patient.mrn}`}
        title={patient.fullName}
        subtitle={`Enrolled on ${new Date(patient.registeredAt).toLocaleDateString()} • Managed by ${patient.clinicName || 'Independent Practice'}`}
        actions={
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setShowArchiveConfirm(true)}
              className="inline-flex items-center gap-1.5 text-xs text-rose-700 hover:text-rose-900 bg-white hover:bg-rose-50 border border-rose-200 px-4 py-2.5 rounded-full font-medium transition-all cursor-pointer shadow-2xs"
            >
              <Archive size={14} />
              <span>Archive</span>
            </button>
            <Link
              href={`/app/screenings/new?patientId=${patient.id}`}
              className="inline-flex items-center gap-1.5 bg-[#4a5320] hover:bg-[#3e461a] text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs hover:shadow no-underline"
            >
              <PlusCircle size={15} />
              <span>New Screening</span>
            </Link>
          </div>
        }
      />

      {/* Archive Confirmation Banner */}
      {showArchiveConfirm && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-900">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-700 shrink-0" />
            <span>Are you sure you want to archive <strong>{patient.fullName}</strong>? The record will be hidden from the active directory.</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setShowArchiveConfirm(false)}
              className="px-3 py-1.5 bg-white border border-amber-300 rounded-full font-medium hover:bg-amber-100/50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleArchive}
              disabled={isArchiving}
              className="px-3.5 py-1.5 bg-rose-700 text-white rounded-full font-semibold hover:bg-rose-800 disabled:opacity-50 flex items-center gap-1"
            >
              {isArchiving ? <Loader2 size={12} className="animate-spin" /> : null}
              <span>Confirm Archive</span>
            </button>
          </div>
        </div>
      )}

      {/* Patient Hero Summary Bar */}
      <div className="p-5 sm:p-6 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-[#4a5320] text-white font-serif font-bold text-lg flex items-center justify-center shrink-0">
            {getInitials(patient.fullName)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-serif text-lg text-[#1c1d1a]">{patient.fullName}</h2>
              <span className="px-2.5 py-0.5 rounded-full bg-[#f2f4e8] text-[#4a5320] font-mono text-[11px] border border-[#d8debe]">
                {patient.mrn}
              </span>
            </div>
            <div className="text-xs text-[#7a7d72] font-mono mt-0.5">
              ID: {patient.id} • Phone: {patient.contactNumber}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {patient.consentGiven ? (
            <>
              <div className="inline-flex items-center gap-1.5 px-3.5 py-1 bg-[#f2f4e8] text-[#4a5320] rounded-full border border-[#d8debe] text-xs font-medium">
                <CheckCircle2 size={13} className="text-[#4a5320]" />
                <span>Informed Consent Granted ({patient.consentDate})</span>
              </div>
              <button
                type="button"
                disabled={updatingConsent}
                onClick={() => handleConsentChange(false)}
                className="text-[11px] font-mono text-rose-700 hover:underline px-2 py-1 cursor-pointer disabled:opacity-50"
              >
                {updatingConsent ? 'Updating...' : 'Revoke'}
              </button>
            </>
          ) : (
            <>
              <div className="inline-flex items-center gap-1.5 px-3.5 py-1 bg-rose-50 text-rose-800 rounded-full border border-rose-200 text-xs font-medium">
                <ShieldAlert size={13} className="text-rose-600" />
                <span>Consent {patient.consentStatus || 'Pending'}</span>
              </div>
              <button
                type="button"
                disabled={updatingConsent}
                onClick={() => handleConsentChange(true)}
                className="inline-flex items-center gap-1 px-3 py-1 bg-[#4a5320] hover:bg-[#3e461a] text-white rounded-full text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {updatingConsent ? 'Recording...' : 'Record Granted Consent'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Patient Clinical Info Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Demographics */}
        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3 text-xs">
          <div className="flex items-center gap-2 pb-2 border-b border-[#e8e4d8]">
            <User size={14} className="text-[#7a7d72]" />
            <span className="text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Demographic Profile
            </span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-[#faf9f5]">
            <span className="text-[#5a5d52]">Age / Gender:</span>
            <span className="font-semibold text-[#1c1d1a]">{patient.age > 0 ? `${patient.age} Yrs` : 'N/A'} / {patient.gender}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-[#faf9f5]">
            <span className="text-[#5a5d52]">Contact:</span>
            <span className="font-mono text-[#1c1d1a]">{patient.contactNumber}</span>
          </div>
          <div className="flex justify-between items-center pt-1">
            <span className="text-[#5a5d52]">Registry Facility:</span>
            <span className="text-[#1c1d1a] font-medium truncate max-w-[140px] text-right">{patient.clinicName || 'Independent'}</span>
          </div>
        </div>

        {/* Card 2: Diabetic History */}
        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3 text-xs">
          <div className="flex items-center gap-2 pb-2 border-b border-[#e8e4d8]">
            <Activity size={14} className="text-[#7a7d72]" />
            <span className="text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Endocrine Profile
            </span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-[#faf9f5]">
            <span className="text-[#5a5d52]">Classification:</span>
            <span className="font-semibold text-[#1c1d1a]">{patient.diabetesType}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-[#faf9f5]">
            <span className="text-[#5a5d52]">Duration:</span>
            <span className="font-mono text-[#1c1d1a]">{patient.diabetesDurationYears} Years</span>
          </div>
          <div className="flex justify-between items-center pt-1">
            <span className="text-[#5a5d52]">Recent HbA1c:</span>
            <span className="font-mono font-bold text-[#1c1d1a]">{patient.recentHbA1c || '—'}</span>
          </div>
        </div>

        {/* Card 3: Clinical Notes */}
        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3 text-xs">
          <div className="flex items-center gap-2 pb-2 border-b border-[#e8e4d8]">
            <FileText size={14} className="text-[#7a7d72]" />
            <span className="text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Clinical Intake Remarks
            </span>
          </div>
          <p className="text-[#5a5d52] leading-relaxed text-xs">
            {patient.notes || 'No pre-existing ocular trauma, vitrectomy, or anti-VEGF injections on record.'}
          </p>
        </div>
      </div>

      {/* Longitudinal Screening Timeline */}
      <div className="p-6 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-4">
        <PatientTimeline
          patientId={patient.id}
          onSelectForComparison={(screeningId) => setCompareModalScreeningId(screeningId)}
        />
      </div>

      {/* Comparison Modal */}
      {compareModalScreeningId && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-[#f5f3ec] border border-[#d8debe] rounded-3xl max-w-5xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-[#e8e4d8]">
              <div className="flex items-center gap-2">
                <GitCompare size={18} className="text-[#4a5320]" />
                <h3 className="font-serif text-lg text-[#1c1d1a]">Longitudinal Screening Comparison</h3>
              </div>
              <button
                type="button"
                onClick={() => setCompareModalScreeningId(null)}
                className="p-1.5 text-[#7a7d72] hover:text-[#1c1d1a] hover:bg-white rounded-full transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <ScreeningComparisonViewer
              currentScreeningId={compareModalScreeningId}
              patientId={patient.id}
            />
          </div>
        </div>
      )}
    </div>
  );
}
