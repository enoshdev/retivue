'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useClinical } from '@/context/ClinicalContext';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/feedback/EmptyState';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import { Search, FileCheck, X, ArrowRight } from 'lucide-react';

export default function ReportsDirectoryPage() {
  const { screenings } = useClinical();
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = screenings.filter((s) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      s.screening_reference.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q) ||
      (s.patient?.full_name || '').toLowerCase().includes(q) ||
      (s.patient?.patient_code || '').toLowerCase().includes(q)
    );
  });

  const readyCount = screenings.filter((s) => s.status === 'ready_for_quality_assessment').length;

  return (
    <div className="space-y-6 pb-16 select-none max-w-7xl mx-auto">
      <PageHeader
        eyebrow="DOCUMENTATION & COMPLIANCE"
        title="Clinical Screening Reports"
        subtitle="Encounter summaries for stored bilateral acquisitions; finalized DR clinical reports become active after Phase 7 analysis"
      />

      <div className="bg-white border border-[#e8e4d8] rounded-2xl shadow-xs overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[#e8e4d8] flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#f5f3ec]">
          <div className="relative flex-1 max-w-md">
            <Search size={15} className="absolute left-3.5 top-2.5 text-[#7a7d72]" />
            <input
              type="text"
              placeholder="Search by patient name, MRN, or screening reference..."
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
            <span>Submitted for QA:</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-white text-[#4a5320] font-semibold font-mono text-[11px] border border-[#d8debe]">
              {readyCount} of {screenings.length}
            </span>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No screening summaries found"
              description="Create a retinal screening and upload bilateral images to inspect technical ingestion records."
              actionLabel="Start New Screening"
              actionHref="/app/screenings/new"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#f5f3ec] border-b border-[#e8e4d8] text-[11px] font-mono uppercase text-[#7a7d72]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Screening Reference</th>
                  <th className="py-3 px-4 font-semibold">Patient Beneficiary</th>
                  <th className="py-3 px-4 font-semibold">Created Date</th>
                  <th className="py-3 px-4 font-semibold">Ingestion Status</th>
                  <th className="py-3 px-4 font-semibold">Clinical Analysis</th>
                  <th className="py-3 px-4 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f5f3ec] font-sans">
                {filtered.map((s) => (
                  <tr key={s.id} className="hover:bg-[#faf9f5] transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center font-mono text-xs font-semibold shrink-0 border border-[#d8debe]">
                          <FileCheck size={14} />
                        </div>
                        <span className="font-mono font-semibold text-[#1c1d1a]">
                          {s.screening_reference}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-[#1c1d1a]">{s.patient?.full_name || 'Patient Record'}</div>
                      <div className="text-[11px] font-mono text-[#7a7d72]">
                        {s.patient?.patient_code || s.patient_id.slice(0, 8)}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-[#5a5d52]">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge type="status" value={s.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-[11px] text-[#7a7d72] font-mono">
                      Awaiting Phase 6 &amp; 7 ML Pipeline
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/app/reports/${s.id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[#1c1d1a] hover:text-[#4a5320] bg-white hover:bg-[#f5f3ec] border border-[#e8e4d8] px-3 py-1 rounded-full transition-colors no-underline shadow-2xs"
                      >
                        <span>View Summary</span>
                        <ArrowRight size={13} />
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
