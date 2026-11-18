'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useClinical } from '@/context/ClinicalContext';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  UserPlus,
  AlertTriangle,
  ShieldCheck,
  User,
  Activity,
  FileText,
  Loader2,
} from 'lucide-react';

export default function NewPatientPage() {
  const router = useRouter();
  const { addPatient, currentUser } = useClinical();

  const [fullName, setFullName] = useState('');
  const [mrn, setMrn] = useState('');
  const [age, setAge] = useState<number>(55);
  const [gender, setGender] = useState<'Male' | 'Female' | 'Other'>('Female');
  const [contactNumber, setContactNumber] = useState('');
  const [diabetesType, setDiabetesType] = useState<'Type 1' | 'Type 2' | 'Gestational' | 'Unknown'>('Type 2');
  const [diabetesDurationYears, setDiabetesDurationYears] = useState<number>(5);
  const [recentHbA1c, setRecentHbA1c] = useState('');
  const [consentGiven, setConsentGiven] = useState(true);
  const [notes, setNotes] = useState('');

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!fullName.trim()) {
      setFormError('Please enter the patient full legal name.');
      return;
    }
    if (!consentGiven) {
      setFormError('Informed clinical screening consent is required before registering.');
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await addPatient({
        fullName: fullName.trim(),
        mrn: mrn.trim() || undefined as unknown as string,
        age: Number(age) || 50,
        gender,
        contactNumber: contactNumber.trim() || 'N/A',
        diabetesType,
        diabetesDurationYears: Number(diabetesDurationYears) || 0,
        recentHbA1c: recentHbA1c.trim() || 'Not tested',
        consentGiven,
        consentDate: new Date().toISOString().split('T')[0],
        registeredBy: currentUser.name,
        clinicName: currentUser.facility,
        notes: notes.trim() || undefined,
      });

      router.push(`/app/patients/${created.id}`);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError('Failed to register patient in database. Please check your network connection.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 pb-16 max-w-2xl mx-auto select-none">
      {/* Page Header */}
      <PageHeader
        backHref="/app/patients"
        backLabel="Back to Directory"
        eyebrow="PATIENT ENROLLMENT"
        title="Register Beneficiary Patient"
        subtitle="Standardized clinical intake form for diabetic eye disease surveillance"
      />

      {formError && (
        <div className="p-4 bg-rose-50 border border-rose-200/80 rounded-xl text-xs text-rose-800 flex items-center gap-2.5">
          <AlertTriangle size={16} className="text-rose-600 shrink-0" />
          <span>{formError}</span>
        </div>
      )}

      {/* Form Card */}
      <form onSubmit={handleSubmit} className="p-6 sm:p-8 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-6">
        {/* Section 1: Demographics */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[#e8e4d8] text-[#1c1d1a]">
            <User size={15} className="text-[#4a5320]" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-[#4a5320]">
              Beneficiary Identity & Demographics
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Full Legal Name *
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Anjali Sharma"
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Medical Record Number (MRN)
              </label>
              <input
                type="text"
                value={mrn}
                onChange={(e) => setMrn(e.target.value)}
                placeholder="Auto-generated if left blank"
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] font-mono placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Contact Phone
              </label>
              <input
                type="tel"
                value={contactNumber}
                onChange={(e) => setContactNumber(e.target.value)}
                placeholder="+91 98765 43210"
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] font-mono placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Age (Years) *
              </label>
              <input
                type="number"
                min={1}
                max={120}
                required
                value={age}
                onChange={(e) => setAge(Number(e.target.value))}
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] font-mono focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Gender *
              </label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value as 'Male' | 'Female' | 'Other')}
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] focus:outline-none focus:border-[#4a5320] transition-all"
              >
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: Endocrine Profile */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[#e8e4d8] text-[#1c1d1a]">
            <Activity size={15} className="text-[#4a5320]" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-[#4a5320]">
              Endocrine Profile & Vitals
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Diabetes Type
              </label>
              <select
                value={diabetesType}
                onChange={(e) => setDiabetesType(e.target.value as 'Type 1' | 'Type 2' | 'Gestational' | 'Unknown')}
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] focus:outline-none focus:border-[#4a5320] transition-all"
              >
                <option value="Type 2">Type 2 (Adult Onset)</option>
                <option value="Type 1">Type 1 (Insulin Dependent)</option>
                <option value="Gestational">Gestational</option>
                <option value="Unknown">Unknown / Pre-diabetic</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Duration (Years)
              </label>
              <input
                type="number"
                min={0}
                max={60}
                value={diabetesDurationYears}
                onChange={(e) => setDiabetesDurationYears(Number(e.target.value))}
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] font-mono focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Recent HbA1c
              </label>
              <input
                type="text"
                value={recentHbA1c}
                onChange={(e) => setRecentHbA1c(e.target.value)}
                placeholder="e.g. 7.2%"
                className="w-full text-xs px-3 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] font-mono placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>
          </div>
        </div>

        {/* Section 3: Clinical Notes */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-[#e8e4d8] text-[#1c1d1a]">
            <FileText size={15} className="text-[#4a5320]" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-[#4a5320]">
              Clinical Intake Notes
            </h3>
          </div>

          <div>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Document visual symptoms, hypertension, prior retinal lasers, anti-VEGF injections, etc..."
              className="w-full text-xs p-3 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-all"
            />
          </div>
        </div>

        {/* Section 4: Informed Consent Safeguard */}
        <div className="p-5 bg-[#f2f4e8] border border-[#d8debe] rounded-2xl space-y-1.5">
          <label className="flex items-start gap-3 text-xs text-[#1c1d1a] cursor-pointer">
            <input
              type="checkbox"
              required
              checked={consentGiven}
              onChange={(e) => setConsentGiven(e.target.checked)}
              className="mt-0.5 rounded border-[#d8debe] text-[#4a5320] focus:ring-0"
            />
            <div className="space-y-0.5">
              <div className="flex items-center gap-1.5 font-semibold text-[#4a5320]">
                <ShieldCheck size={14} className="text-[#4a5320] shrink-0" />
                <span>Informed Screening Consent Verified</span>
              </div>
              <p className="text-[11px] text-[#5a5d52] leading-relaxed">
                Patient has been informed that this screening employs an AI decision support tool to inspect retinal photographs and does not constitute a full ophthalmic surgical or medical diagnosis.
              </p>
            </div>
          </label>
        </div>

        {/* Action Buttons */}
        <div className="pt-3 flex items-center justify-between border-t border-[#e8e4d8]">
          <Link
            href="/app/patients"
            className="text-xs text-[#7a7d72] hover:text-[#1c1d1a] no-underline font-medium"
          >
            Cancel
          </Link>

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] disabled:opacity-60 text-white text-xs font-semibold px-6 py-3 rounded-full transition-all shadow-sm hover:shadow cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                <span>Registering Patient to Database...</span>
              </>
            ) : (
              <>
                <UserPlus size={15} />
                <span>Complete Registration & Open Profile</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

