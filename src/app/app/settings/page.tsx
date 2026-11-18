'use client';

import React, { useState } from 'react';
import { useClinical } from '@/context/ClinicalContext';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  User,
  Building2,
  CheckCircle2,
  AlertCircle,
  Shield,
  Sliders,
  Save,
  Loader2,
} from 'lucide-react';

export default function SettingsPage() {
  const { currentUser, updateCurrentUser } = useClinical();

  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [clinicianName, setClinicianName] = useState(currentUser.name);
  const [facilityName, setFacilityName] = useState(currentUser.facility);
  const [regNumber, setRegNumber] = useState(currentUser.registrationNumber || '');
  const [prevUser, setPrevUser] = useState(currentUser);
  const [defaultStagingProtocol, setDefaultStagingProtocol] = useState<'ICDR' | 'ETDRS'>('ICDR');
  const [redFreeDefault, setRedFreeDefault] = useState(false);

  // Synchronize when currentUser loads from backend
  if (currentUser.id !== prevUser.id || currentUser.name !== prevUser.name) {
    setPrevUser(currentUser);
    if (currentUser.name && currentUser.name !== 'Unauthenticated User') {
      setClinicianName(currentUser.name);
      setFacilityName(currentUser.facility || '');
      setRegNumber(currentUser.registrationNumber || '');
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);
    try {
      await updateCurrentUser({
        full_name: clinicianName.trim(),
        facility_name: facilityName.trim(),
        registration_number: regNumber.trim(),
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to save profile changes.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const getInitials = (name: string) => {
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <div className="space-y-6 pb-16 select-none max-w-3xl mx-auto">
      {/* Header */}
      <PageHeader
        eyebrow="CONFIGURATION & PROFILE"
        title="Account & Practice Settings"
        subtitle="Manage clinician credentials, facility affiliations, and decision-support defaults"
      />

      {savedSuccess && (
        <div className="p-4 bg-[#f2f4e8] border border-[#d8debe] rounded-2xl text-xs text-[#4a5320] flex items-center gap-2.5 animate-in fade-in duration-200">
          <CheckCircle2 size={16} className="text-[#4a5320] shrink-0" />
          <span className="font-semibold">Settings saved successfully. Changes persisted to database.</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-xs text-rose-800 flex items-center gap-2.5 animate-in fade-in duration-200">
          <AlertCircle size={16} className="text-rose-600 shrink-0" />
          <span className="font-semibold">{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Clinician Profile */}
        <div className="p-6 sm:p-7 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-[#e8e4d8]">
            <div className="flex items-center gap-2 text-[#1c1d1a]">
              <User size={16} className="text-[#4a5320]" />
              <h2 className="text-xs font-bold font-mono uppercase tracking-wider text-[#6f7d3e]">
                Clinician Identity & Verification
              </h2>
            </div>
            <span className="inline-flex items-center gap-1 text-[11px] font-mono text-[#4a5320] bg-[#f2f4e8] px-2.5 py-0.5 rounded-full border border-[#d8debe]">
              <Shield size={11} /> Verified Clinician
            </span>
          </div>

          <div className="flex items-center gap-4 py-1">
            <div className="w-14 h-14 rounded-full bg-[#4a5320] text-white font-serif font-bold text-xl flex items-center justify-center shrink-0 shadow-xs">
              {getInitials(clinicianName)}
            </div>
            <div>
              <div className="text-base font-serif text-[#1c1d1a]">{clinicianName}</div>
              <div className="text-xs text-[#7a7d72] font-mono mt-0.5">{currentUser.email}</div>
              <div className="text-[11px] text-[#4a5320] font-mono mt-0.5 font-semibold">Unified Clinician Account</div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-1">
            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Full Legal Name
              </label>
              <input
                type="text"
                value={clinicianName}
                onChange={(e) => setClinicianName(e.target.value)}
                className="w-full px-3 py-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Institutional Email (Locked)
              </label>
              <input
                type="email"
                disabled
                value={currentUser.email}
                className="w-full px-3 py-2 bg-[#f5f3ec] border border-[#e8e4d8] rounded-xl text-[#7a7d72] font-mono cursor-not-allowed text-xs"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Medical Council Registration #
              </label>
              <input
                type="text"
                value={regNumber}
                onChange={(e) => setRegNumber(e.target.value)}
                className="w-full px-3 py-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] font-mono focus:outline-none focus:border-[#4a5320] transition-all text-xs"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Active System Profile
              </label>
              <input
                type="text"
                disabled
                value="Verified Clinician / Operator"
                className="w-full px-3 py-2 bg-[#f5f3ec] border border-[#e8e4d8] rounded-xl text-[#4a5320] font-mono cursor-not-allowed text-xs font-semibold"
              />
            </div>
          </div>
        </div>

        {/* Facility Info */}
        <div className="p-6 sm:p-7 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-[#e8e4d8] text-[#1c1d1a]">
            <Building2 size={16} className="text-[#4a5320]" />
            <h2 className="text-xs font-bold font-mono uppercase tracking-wider text-[#6f7d3e]">
              Practice & Facility Affiliation
            </h2>
          </div>

          <div className="text-xs space-y-3">
            <div>
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold mb-1">
                Practice / Facility Name
              </label>
              <input
                type="text"
                value={facilityName}
                onChange={(e) => setFacilityName(e.target.value)}
                className="w-full px-3 py-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-[#1c1d1a] focus:outline-none focus:border-[#4a5320] transition-all"
              />
            </div>

            <p className="text-[11px] text-[#5a5d52] leading-relaxed bg-[#faf9f5] p-3.5 rounded-xl border border-[#e8e4d8] font-mono">
              Independent ophthalmologists can operate without an institutional clinic affiliation. Clinical review encounters and exported reports will be stamped with your individual registration credentials.
            </p>
          </div>
        </div>

        {/* Clinical Workspace Preferences */}
        <div className="p-6 sm:p-7 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-[#e8e4d8] text-[#1c1d1a]">
            <Sliders size={16} className="text-[#4a5320]" />
            <h2 className="text-xs font-bold font-mono uppercase tracking-wider text-[#6f7d3e]">
              Clinical Workspace Preferences
            </h2>
          </div>

          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between py-1">
              <div>
                <div className="font-semibold text-[#1c1d1a]">Default Grading Scale</div>
                <div className="text-[11px] text-[#7a7d72]">Choose between International ICDR or ETDRS-7 standard classification</div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setDefaultStagingProtocol('ICDR')}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
                    defaultStagingProtocol === 'ICDR'
                      ? 'bg-[#4a5320] text-white shadow-xs'
                      : 'bg-[#f5f3ec] text-[#4a4c44] hover:bg-[#edeae0]'
                  }`}
                >
                  ICDR (5-Level)
                </button>
                <button
                  type="button"
                  onClick={() => setDefaultStagingProtocol('ETDRS')}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
                    defaultStagingProtocol === 'ETDRS'
                      ? 'bg-[#4a5320] text-white shadow-xs'
                      : 'bg-[#f5f3ec] text-[#4a4c44] hover:bg-[#edeae0]'
                  }`}
                >
                  ETDRS
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between py-1 border-t border-[#e8e4d8]">
              <div>
                <div className="font-semibold text-[#1c1d1a]">Auto-Apply Red-Free (540nm) Optical Filter</div>
                <div className="text-[11px] text-[#7a7d72]">Automatically activate monochromatic green filter on workspace launch to highlight microaneurysms</div>
              </div>
              <input
                type="checkbox"
                checked={redFreeDefault}
                onChange={(e) => setRedFreeDefault(e.target.checked)}
                className="w-4 h-4 rounded text-[#4a5320] focus:ring-0 border-[#d8debe]"
              />
            </div>
          </div>
        </div>

        {/* Save CTA */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center gap-2 px-7 py-3 bg-[#4a5320] hover:bg-[#3e461a] disabled:opacity-60 text-white rounded-full text-xs font-semibold transition-all shadow-sm hover:shadow cursor-pointer"
          >
            {isSaving ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                <span>Saving Changes...</span>
              </>
            ) : (
              <>
                <Save size={15} />
                <span>Save Configuration</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
