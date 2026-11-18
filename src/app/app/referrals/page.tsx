'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/feedback/EmptyState';
import { clinicalWorkflowApi, ReferralResponse } from '@/lib/api';
import { Building2, Calendar, FileText, ArrowRight, Loader2, RefreshCw } from 'lucide-react';

export default function ReferralsTrackerPage() {
  const [referrals, setReferrals] = useState<ReferralResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const loadReferrals = async () => {
    setLoading(true);
    try {
      const data = await clinicalWorkflowApi.listReferrals();
      setReferrals(data);
    } catch {
      setReferrals([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    clinicalWorkflowApi
      .listReferrals()
      .then((data) => {
        if (active) {
          setReferrals(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setReferrals([]);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6 pb-16 select-none max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          eyebrow="TERTIARY CARE HAND-OFF"
          title="Specialist Referrals Tracker"
          subtitle="Ophthalmology referrals dispatched strictly following independent clinical sign-off"
        />
        <button
          onClick={loadReferrals}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] rounded-full hover:bg-[#e4ebc8] transition-colors self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="p-16 text-center text-xs text-[#7a7d72] flex items-center justify-center gap-2 bg-white rounded-2xl border border-[#e8e4d8]">
          <Loader2 size={16} className="animate-spin text-[#4a5320]" />
          <span>Loading specialist referrals...</span>
        </div>
      ) : referrals.length === 0 ? (
        <div className="bg-white border border-[#e8e4d8] rounded-2xl p-8 shadow-xs">
          <EmptyState
            title="No specialist referrals dispatched"
            description="Referrals can be generated from the screening workspace once an authorized healthcare professional signs off on the clinical assessment."
            actionLabel="View Screening Encounters"
            actionHref="/app/screenings"
          />
        </div>
      ) : (
        <div className="bg-white border border-[#e8e4d8] rounded-2xl shadow-xs overflow-hidden">
          <div className="divide-y divide-[#e8e4d8]">
            {referrals.map((ref) => (
              <div key={ref.id} className="p-5 hover:bg-[#faf9f5] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-[#1c1d1a] bg-[#f5f3ec] px-2.5 py-0.5 rounded-md border border-[#e8e4d8]">
                      {ref.referral_reference}
                    </span>
                    <span className="font-semibold text-sm text-[#1c1d1a]">
                      {ref.patient_name || 'Patient'}
                    </span>
                    {ref.patient_mrn && (
                      <span className="text-xs font-mono text-[#7a7d72]">({ref.patient_mrn})</span>
                    )}
                    <span
                      className={`text-[10px] font-semibold font-mono px-2 py-0.5 rounded-full ${
                        ref.urgency === 'IMMEDIATE_48H'
                          ? 'bg-rose-100 text-rose-900 border border-rose-300'
                          : ref.urgency === 'WITHIN_2_WEEKS'
                          ? 'bg-amber-100 text-amber-900 border border-amber-300'
                          : 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                      }`}
                    >
                      {ref.urgency.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div className="text-xs text-[#5a5d52] flex items-center gap-3 flex-wrap">
                    <span className="flex items-center gap-1">
                      <Building2 size={13} className="text-[#4a5320]" />
                      <strong>{ref.target_facility}</strong> ({ref.target_specialty})
                    </span>
                    <span className="flex items-center gap-1 font-mono text-[#7a7d72]">
                      <Calendar size={13} />
                      {new Date(ref.dispatched_at).toLocaleDateString()}
                    </span>
                  </div>

                  <p className="text-xs text-[#7a7d72] line-clamp-2 max-w-2xl">
                    {ref.reason_summary}
                  </p>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end md:self-auto">
                  <span className="text-xs font-mono font-medium px-2.5 py-1 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe]">
                    {ref.status}
                  </span>
                  <Link
                    href={`/app/reports/${ref.screening_id}`}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-[#4a5320] hover:bg-[#3e461a] rounded-full transition-colors no-underline"
                  >
                    <FileText size={13} />
                    <span>Report</span>
                    <ArrowRight size={13} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
