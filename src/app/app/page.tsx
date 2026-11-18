'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useClinical } from '@/context/ClinicalContext';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import { CdsDisclaimerBanner } from '@/components/clinical/CdsDisclaimerBanner';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/feedback/EmptyState';
import {
  PlusCircle,
  ArrowRight,
  Layers,
  Users,
  CheckCircle2,
  Clock,
  Camera,
  ChevronRight,
  UserPlus,
  BookOpen,
} from 'lucide-react';

export default function UnifiedDashboardPage() {
  const router = useRouter();
  const { currentUser, screenings, screeningsTotal, patients, patientsTotal } = useClinical();

  const readyCount = screenings.filter((s) => s.status === 'ready_for_quality_assessment').length;
  const incompleteCount = screenings.filter(
    (s) => s.status === 'awaiting_images' || s.status === 'images_incomplete' || s.status === 'draft'
  ).length;

  return (
    <div className="space-y-6 pb-12 select-none max-w-7xl mx-auto">
      {/* Clinician Welcome Header */}
      <PageHeader
        eyebrow={`DIABETIC RETINOPATHY SCREENING PLATFORM • ${currentUser.facility}`}
        title={`Welcome, ${currentUser.name}`}
        subtitle="Manage patient records, acquire bilateral retinal fundus photographs, and prepare encounters for quality assessment"
        actions={
          <div className="flex items-center gap-2.5">
            <Link
              href="/app/patients/new"
              className="inline-flex items-center gap-1.5 bg-white hover:bg-[#f5f3ec] text-[#1c1d1a] border border-[#e8e4d8] px-4 py-2.5 rounded-full text-xs font-semibold transition-all shadow-2xs no-underline"
            >
              <UserPlus size={14} />
              <span>Add Patient</span>
            </Link>
            <Link
              href="/app/screenings/new"
              className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs no-underline"
            >
              <PlusCircle size={15} />
              <span>Start New Screening</span>
            </Link>
          </div>
        }
      />

      <CdsDisclaimerBanner compact />

      {/* Actual Database Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#7a7d72]">
            <span className="font-medium">Total Screenings</span>
            <Layers size={16} className="text-[#4a5320]" />
          </div>
          <div className="text-3xl font-serif text-[#1c1d1a]">
            {screeningsTotal || screenings.length}
          </div>
          <p className="text-[11px] text-[#7a7d72]">Stored in PostgreSQL</p>
        </div>

        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#7a7d72]">
            <span className="font-medium">Patients</span>
            <Users size={16} className="text-[#6f7d3e]" />
          </div>
          <div className="text-3xl font-serif text-[#1c1d1a]">
            {patientsTotal || patients.length}
          </div>
          <p className="text-[11px] text-[#7a7d72]">Registered beneficiaries</p>
        </div>

        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#7a7d72]">
            <span className="font-medium">Ready for QA</span>
            <CheckCircle2 size={16} className="text-emerald-700" />
          </div>
          <div className="text-3xl font-serif text-[#1c1d1a]">
            {readyCount}
          </div>
          <p className="text-[11px] text-emerald-800 font-medium">Bilateral &amp; consent verified</p>
        </div>

        <div className="p-5 bg-white border border-[#e8e4d8] rounded-2xl shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#7a7d72]">
            <span className="font-medium">Drafts / Incomplete</span>
            <Clock size={16} className="text-amber-700" />
          </div>
          <div className="text-3xl font-serif text-[#1c1d1a]">
            {incompleteCount}
          </div>
          <p className="text-[11px] text-amber-800 font-medium">Pending images or submission</p>
        </div>
      </div>

      {/* Main Two-Column Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between pb-1">
            <h3 className="font-serif text-lg text-[#1c1d1a]">Recent Screening Encounters</h3>
            <Link
              href="/app/screenings"
              className="text-xs text-[#6f7d3e] hover:text-[#4a5320] font-semibold no-underline flex items-center gap-1"
            >
              <span>View All</span>
              <ChevronRight size={13} />
            </Link>
          </div>

          <div className="bg-white border border-[#e8e4d8] rounded-2xl shadow-2xs overflow-hidden">
            {screenings.length > 0 ? (
              <div className="divide-y divide-[#e8e4d8]">
                {screenings.slice(0, 5).map((s) => (
                  <div
                    key={s.id}
                    className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#faf9f5] transition-colors"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="font-mono text-xs font-bold text-[#1c1d1a]">
                          {s.screening_reference}
                        </span>
                        <StatusBadge type="status" value={s.status} size="sm" />
                      </div>
                      <div className="text-xs text-[#4a4c44]">
                        <strong className="text-[#1c1d1a]">{s.patient?.full_name || 'Patient Record'}</strong>
                        <span className="text-[#7a7d72] mx-1.5">•</span>
                        <span className="font-mono text-[11px] text-[#7a7d72]">
                          {s.patient?.patient_code || s.patient_id.slice(0, 8)}
                        </span>
                        <span className="text-[#7a7d72] mx-1.5">•</span>
                        <span className="text-[11px] text-[#7a7d72]">
                          {new Date(s.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <Link
                        href={`/app/screenings/${s.id}`}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#f2f4e8] hover:bg-[#e7edd3] text-[#4a5320] text-xs font-semibold border border-[#d8debe] transition-colors no-underline"
                      >
                        <span>Open Workspace</span>
                        <ArrowRight size={13} />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center">
                <EmptyState
                  title="No screening encounters recorded yet"
                  description="Begin by registering a patient and uploading bilateral JPEG or PNG retinal images."
                  actionLabel="Start New Screening"
                  onAction={() => router.push('/app/screenings/new')}
                />
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Patients Summary & Optical Reference */}
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1">
              <h3 className="font-serif text-lg text-[#1c1d1a]">Registered Patients</h3>
              <Link
                href="/app/patients"
                className="text-xs text-[#6f7d3e] hover:text-[#4a5320] font-semibold no-underline flex items-center gap-1"
              >
                <span>View All</span>
                <ChevronRight size={13} />
              </Link>
            </div>

            <div className="bg-white border border-[#e8e4d8] rounded-2xl p-4 shadow-2xs space-y-3">
              {patients.length > 0 ? (
                <div className="divide-y divide-[#e8e4d8]">
                  {patients.slice(0, 4).map((p) => (
                    <div key={p.id} className="py-2.5 flex items-center justify-between">
                      <div>
                        <Link
                          href={`/app/patients/${p.id}`}
                          className="text-xs font-semibold text-[#1c1d1a] hover:text-[#4a5320] no-underline block"
                        >
                          {p.fullName}
                        </Link>
                        <span className="font-mono text-[10px] text-[#7a7d72]">
                          {p.mrn} • {p.age} Yrs • {p.diabetesType}
                        </span>
                      </div>
                      <Link
                        href={`/app/screenings/new?patientId=${p.id}`}
                        className="text-[11px] text-[#4a5320] hover:underline font-medium"
                      >
                        Screen
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 space-y-2.5">
                  <p className="text-xs text-[#7a7d72]">No patients registered in your account yet.</p>
                  <Link
                    href="/app/patients/new"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#faf9f5] border border-[#e8e4d8] text-xs font-medium text-[#1c1d1a] hover:bg-[#f5f3ec] no-underline"
                  >
                    <UserPlus size={13} />
                    <span>Register First Patient</span>
                  </Link>
                </div>
              )}
            </div>
          </div>

          <div className="p-5 bg-[#f5f3ec] border border-[#e8e4d8] rounded-2xl space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#1c1d1a]">
              <Camera size={15} className="text-[#4a5320]" />
              <span>Optical Acquisition Standards</span>
            </div>
            <p className="text-[11px] text-[#5a5d52] leading-relaxed">
              Standard bilateral screening requires high-resolution JPEG or PNG 45° fundus captures for both Right Eye (OD) and Left Eye (OS). Original bytes are stored privately without lossy modification.
            </p>
            <div className="pt-1">
              <Link
                href="/how-it-works"
                className="inline-flex items-center gap-1 text-[11px] text-[#4a5320] hover:underline font-semibold no-underline"
              >
                <BookOpen size={13} />
                <span>Review Imaging Protocols →</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
