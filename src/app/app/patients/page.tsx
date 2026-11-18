'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useClinical } from '@/context/ClinicalContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/feedback/EmptyState';
import {
  UserPlus,
  Search,
  ArrowRight,
  CheckCircle2,
  X,
  RotateCcw,
  Loader2,
} from 'lucide-react';

export default function PatientsDirectoryPage() {
  const { patients, patientsLoading, refreshPatients } = useClinical();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredPatients = patients.filter((p) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      p.fullName.toLowerCase().includes(q) ||
      p.mrn.toLowerCase().includes(q) ||
      p.id.toLowerCase().includes(q) ||
      p.contactNumber.includes(q)
    );
  });

  const getInitials = (name: string) => {
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <div className="space-y-6 pb-16 select-none max-w-7xl mx-auto">
      {/* Top Header */}
      <PageHeader
        eyebrow="BENEFICIARY REGISTRY"
        title="Patient Directory"
        subtitle="Registered diabetic individuals with consent status and longitudinal screening history"
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => refreshPatients(searchQuery)}
              disabled={patientsLoading}
              title="Refresh Registry"
              className="p-2.5 bg-white hover:bg-[#f5f3ec] border border-[#e8e4d8] text-[#4a4c44] rounded-full transition-all shadow-2xs cursor-pointer"
            >
              <RotateCcw size={14} className={patientsLoading ? 'animate-spin' : ''} />
            </button>
            <Link
              href="/app/patients/new"
              className="inline-flex items-center gap-1.5 bg-[#4a5320] hover:bg-[#3e461a] text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs hover:shadow no-underline"
            >
              <UserPlus size={15} />
              <span>Register New Patient</span>
            </Link>
          </div>
        }
      />

      {/* Main Container */}
      <div className="bg-white border border-[#e8e4d8] rounded-2xl shadow-xs overflow-hidden">
        {/* Search Bar Header */}
        <div className="p-4 sm:p-5 border-b border-[#e8e4d8] flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#f5f3ec]">
          <div className="relative flex-1 max-w-md">
            <Search size={15} className="absolute left-3.5 top-2.5 text-[#7a7d72]" />
            <input
              type="text"
              placeholder="Search by name, MRN, ID, or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-9 py-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-all shadow-2xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-2.5 text-[#7a7d72] hover:text-[#1c1d1a]"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-[#5a5d52] font-mono">
            <span>Enrolled Beneficiaries:</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-white text-[#4a5320] font-semibold font-mono text-[11px] border border-[#d8debe]">
              {filteredPatients.length} of {patients.length}
            </span>
          </div>
        </div>

        {patientsLoading && patients.length === 0 ? (
          <div className="p-12 text-center text-xs text-[#7a7d72] flex flex-col items-center justify-center gap-3">
            <Loader2 size={24} className="animate-spin text-[#4a5320]" />
            <span>Loading patient directory from database...</span>
          </div>
        ) : filteredPatients.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title={patients.length === 0 ? "No patients registered yet" : "No patients match your query"}
              description={
                patients.length === 0
                  ? "Your patient directory is currently empty. Register your first patient to begin screening and review."
                  : "No registered patient records match your current search criteria."
              }
              actionLabel="Register New Patient"
              actionHref="/app/patients/new"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#f5f3ec] border-b border-[#e8e4d8] text-[11px] font-mono uppercase text-[#7a7d72]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Patient Beneficiary</th>
                  <th className="py-3 px-4 font-semibold">Demographics</th>
                  <th className="py-3 px-4 font-semibold">Endocrine Profile</th>
                  <th className="py-3 px-4 font-semibold">HbA1c</th>
                  <th className="py-3 px-4 font-semibold">Consent</th>
                  <th className="py-3 px-4 font-semibold">Encounters</th>
                  <th className="py-3 px-4 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f5f3ec] font-sans">
                {filteredPatients.map((p) => (
                  <tr key={p.id} className="hover:bg-[#faf9f5] transition-colors group">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-[#f2f4e8] border border-[#d8debe] text-[#4a5320] flex items-center justify-center font-serif text-sm font-semibold shrink-0 group-hover:bg-[#4a5320] group-hover:text-white transition-colors">
                          {getInitials(p.fullName)}
                        </div>
                        <div>
                          <Link
                            href={`/app/patients/${p.id}`}
                            className="font-semibold text-[#1c1d1a] hover:text-[#4a5320] transition-colors no-underline text-xs"
                          >
                            {p.fullName}
                          </Link>
                          <div className="text-[11px] font-mono text-[#7a7d72] mt-0.5">
                            {p.mrn}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-[#5a5d52]">
                      {p.age > 0 ? `${p.age}y` : 'Age N/A'} / {p.gender}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-[#1c1d1a]">{p.diabetesType}</div>
                      <div className="text-[11px] text-[#7a7d72] font-mono mt-0.5">
                        {p.diabetesDurationYears} yrs duration
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-[#1c1d1a]">
                      {p.recentHbA1c || '—'}
                    </td>
                    <td className="py-3 px-4">
                      {p.consentGiven ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-[#4a5320] bg-[#f2f4e8] px-2.5 py-0.5 rounded-full border border-[#d8debe]">
                          <CheckCircle2 size={12} />
                          <span>Verified</span>
                        </span>
                      ) : (
                        <span className="text-[11px] font-mono text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200">
                          Pending
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-[#5a5d52]">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-[#f5f3ec] text-[#4a5320] text-[11px] border border-[#e8e4d8]">
                        {p.screeningCount} {p.screeningCount === 1 ? 'case' : 'cases'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/app/patients/${p.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[#1c1d1a] hover:text-[#4a5320] bg-white hover:bg-[#f5f3ec] border border-[#e8e4d8] px-3 py-1 rounded-full transition-colors no-underline"
                      >
                        <span>Profile</span>
                        <ArrowRight size={12} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
