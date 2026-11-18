'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ApiScreening, ScreeningLifecycleStatus, screeningApi } from '@/lib/api';
import { StatusBadge } from '@/components/clinical/StatusBadge';
import { CdsDisclaimerBanner } from '@/components/clinical/CdsDisclaimerBanner';
import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/feedback/EmptyState';
import {
  PlusCircle,
  Search,
  ArrowRight,
  Loader2,
  AlertTriangle,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  CircleDashed,
} from 'lucide-react';

export default function ScreeningQueuePage() {
  const [items, setItems] = useState<ApiScreening[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(0);
  const pageSize = 10;

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState<number>(0);

  const refreshManually = useCallback(() => {
    setLoading(true);
    setError(null);
    setRefreshTick((t) => t + 1);
  }, []);

  useEffect(() => {
    let active = true;
    screeningApi
      .list({
        page,
        page_size: pageSize,
        status: statusFilter === 'ALL' ? undefined : (statusFilter as ScreeningLifecycleStatus),
      })
      .then((res) => {
        if (!active) return;
        setItems(res.items);
        setTotal(res.total);
        setTotalPages(res.total_pages);
        setError(null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Unable to fetch screening records from database.');
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page, statusFilter, refreshTick]);

  const handleStatusChange = (nextStatus: string) => {
    setLoading(true);
    setStatusFilter(nextStatus);
    setPage(1);
  };

  const filteredItems = items.filter((s) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      s.screening_reference.toLowerCase().includes(q) ||
      s.id.toLowerCase().includes(q) ||
      (s.patient?.full_name || '').toLowerCase().includes(q) ||
      (s.patient?.patient_code || '').toLowerCase().includes(q) ||
      (s.camera_model || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6 pb-16 select-none max-w-7xl mx-auto">
      <PageHeader
        eyebrow="CENTRAL ENCOUNTERS REGISTRY"
        title="Retinal Screening History"
        subtitle="Account-isolated screening encounters, bilateral capture progress, and submission readiness"
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={refreshManually}
              disabled={loading}
              title="Refresh Screenings"
              className="p-2.5 bg-white hover:bg-[#f5f3ec] border border-[#e8e4d8] text-[#4a4c44] rounded-full transition-all shadow-2xs cursor-pointer"
            >
              <RotateCcw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            <Link
              href="/app/screenings/new"
              className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-all shadow-xs no-underline"
            >
              <PlusCircle size={15} />
              <span>New Retinal Screening</span>
            </Link>
          </div>
        }
      />

      <CdsDisclaimerBanner compact />

      <div className="p-5 sm:p-6 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
            <input
              type="text"
              placeholder="Filter current page by Patient Name, MRN, Reference (SCR-...), or Camera..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
            />
          </div>

          <div className="flex flex-wrap items-center gap-1 p-1 bg-[#edebe1] rounded-full text-xs font-mono shrink-0">
            {[
              { id: 'ALL', label: `All (${total})` },
              { id: 'awaiting_images', label: 'Awaiting Images' },
              { id: 'images_incomplete', label: 'Incomplete' },
              { id: 'draft', label: 'Bilateral Draft' },
              { id: 'ready_for_quality_assessment', label: 'Ready for QA' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleStatusChange(tab.id)}
                className={`px-3 py-1 rounded-full transition-all cursor-pointer ${
                  statusFilter === tab.id
                    ? 'bg-[#4a5320] text-white font-semibold shadow-xs'
                    : 'text-[#4a4c44] hover:text-[#1c1d1a]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="p-12 text-center text-xs text-[#7a7d72] flex flex-col items-center justify-center gap-3">
            <Loader2 size={24} className="animate-spin text-[#4a5320]" />
            <span>Loading screening encounters from PostgreSQL...</span>
          </div>
        ) : error ? (
          /* Error State */
          <div className="p-8 bg-rose-50 border border-rose-200 rounded-2xl text-center space-y-3">
            <AlertTriangle size={24} className="text-rose-600 mx-auto" />
            <div className="text-xs font-semibold text-rose-900">Failed to Load Screening Records</div>
            <p className="text-xs text-rose-800 max-w-md mx-auto">{error}</p>
            <button
              type="button"
              onClick={refreshManually}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-700 hover:bg-rose-800 text-white rounded-full text-xs font-semibold cursor-pointer"
            >
              <RotateCcw size={13} />
              <span>Retry Query</span>
            </button>
          </div>
        ) : filteredItems.length === 0 ? (
          /* Empty State */
          <EmptyState
            title={total === 0 && statusFilter === 'ALL' ? 'No screening encounters recorded yet' : 'No matching screenings found'}
            description={
              total === 0 && statusFilter === 'ALL'
                ? 'Start a new retinal screening for an enrolled patient and upload OD/OS fundus photographs.'
                : 'Clear your search query or change the lifecycle filter to view other encounters.'
            }
            actionLabel={total === 0 && statusFilter === 'ALL' ? 'Start New Screening' : 'Reset Filters'}
            onAction={
              total === 0 && statusFilter === 'ALL'
                ? undefined
                : () => {
                    setSearchQuery('');
                    setStatusFilter('ALL');
                    setPage(1);
                  }
            }
            actionHref={total === 0 && statusFilter === 'ALL' ? '/app/screenings/new' : undefined}
          />
        ) : (
          <>
            <div className="overflow-x-auto border border-[#e8e4d8] rounded-2xl">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#f5f3ec] border-b border-[#e8e4d8] text-[11px] font-mono uppercase text-[#7a7d72]">
                  <tr>
                    <th className="py-3 px-3.5">Screening Reference</th>
                    <th className="py-3 px-3.5">Patient Beneficiary</th>
                    <th className="py-3 px-3.5">Created Date</th>
                    <th className="py-3 px-3.5">Bilateral Capture</th>
                    <th className="py-3 px-3.5">Lifecycle Status</th>
                    <th className="py-3 px-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#f5f3ec] font-sans">
                  {filteredItems.map((s) => (
                    <tr key={s.id} className="hover:bg-[#faf9f5] transition-colors">
                      <td className="py-3 px-3.5">
                        <div className="font-mono font-semibold text-[#1c1d1a]">
                          {s.screening_reference}
                        </div>
                        <div className="text-[11px] text-[#7a7d72] truncate max-w-[200px]">
                          {s.camera_model || 'Standard Fundus Camera'}
                        </div>
                      </td>
                      <td className="py-3 px-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center font-bold text-xs shrink-0 border border-[#d8debe]">
                            {(s.patient?.full_name || 'P').charAt(0)}
                          </div>
                          <div>
                            <Link
                              href={`/app/patients/${s.patient_id}`}
                              className="font-semibold text-[#1c1d1a] hover:text-[#4a5320] no-underline"
                            >
                              {s.patient?.full_name || 'Patient Record'}
                            </Link>
                            <div className="text-[11px] font-mono text-[#7a7d72]">
                              {s.patient?.patient_code || s.patient_id.slice(0, 8)}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-3.5 font-mono text-xs text-[#5a5d52]">
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-3.5 font-mono text-[11px]">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${
                              s.has_od_image
                                ? 'bg-[#f2f4e8] text-[#4a5320] border-[#d8debe]'
                                : 'bg-[#faf9f5] text-[#7a7d72] border-[#e8e4d8]'
                            }`}
                          >
                            {s.has_od_image ? <CheckCircle2 size={11} /> : <CircleDashed size={11} />}
                            OD
                          </span>
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${
                              s.has_os_image
                                ? 'bg-[#f2f4e8] text-[#4a5320] border-[#d8debe]'
                                : 'bg-[#faf9f5] text-[#7a7d72] border-[#e8e4d8]'
                            }`}
                          >
                            {s.has_os_image ? <CheckCircle2 size={11} /> : <CircleDashed size={11} />}
                            OS
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3.5">
                        <StatusBadge type="status" value={s.status} size="sm" />
                      </td>
                      <td className="py-3 px-3.5 text-right">
                        <Link
                          href={`/app/screenings/${s.id}`}
                          className="inline-flex items-center gap-1.5 bg-[#4a5320] hover:bg-[#3e461a] text-white px-3.5 py-1.5 rounded-full text-xs font-semibold no-underline transition-colors shadow-2xs"
                        >
                          <span>{s.is_bilateral_complete ? 'Inspect' : 'Continue'}</span>
                          <ArrowRight size={13} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Footer */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 text-xs text-[#7a7d72] font-mono">
              <span>
                Showing page {page} of {Math.max(1, totalPages)} ({total} total records)
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-[#e8e4d8] bg-white text-[#1c1d1a] hover:bg-[#f5f3ec] disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                >
                  <ChevronLeft size={13} />
                  <span>Previous</span>
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-[#e8e4d8] bg-white text-[#1c1d1a] hover:bg-[#f5f3ec] disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                >
                  <span>Next</span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
