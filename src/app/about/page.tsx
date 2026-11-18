'use client';

import React from 'react';
import Link from 'next/link';
import { PublicLayout } from '@/layouts/PublicLayout';
import { ArrowRight, ShieldCheck } from 'lucide-react';

export default function AboutPage() {
  return (
    <PublicLayout>
      <div className="py-20 md:py-28 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 select-none">
        {/* Header */}
        <div className="mb-12">
          <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
            MISSION & CLINICAL OBJECTIVES
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
            About Retivue
          </h1>
          <p className="mt-4 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
            Retivue is an AI-assisted retinal screening and clinical decision-support platform designed to address the preventable blindness burden of diabetic retinopathy in the Indian healthcare ecosystem.
          </p>
        </div>

        {/* Core Content Blocks */}
        <div className="space-y-6 text-[#1c1d1a] leading-relaxed">
          <section className="p-8 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3">
            <h2 className="font-serif text-xl text-[#1c1d1a]">
              What Retivue Is
            </h2>
            <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
              Retivue is an adjunct clinical decision-support (CADe) software platform built for ophthalmologists, optometrists, and vision technicians. It ingests 45° non-mydriatic fundus photographs, executes pre-flight ISO 10940 optical quality verification, highlights suspect microvascular lesions, and formats findings for structured ophthalmological review.
            </p>
          </section>

          <section className="p-8 bg-white border border-[#e8e4d8] rounded-2xl shadow-xs space-y-3">
            <h2 className="font-serif text-xl text-[#1c1d1a]">
              Target Problem in the Indian Healthcare Ecosystem
            </h2>
            <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
              Diabetic retinopathy is a leading cause of preventable visual loss in India. Over 70% of diabetic individuals in rural regions have never received a fundus examination due to the geographic concentration of vitreoretinal specialists in tier-1 cities. By enabling mobile vision technicians and independent ophthalmologists to conduct tele-screenings with automated quality checks, Retivue accelerates early referral before irreversible macular edema or proliferative disease occurs.
            </p>
          </section>

          <section className="p-8 bg-[#f5f3ec] border border-[#e8e4d8] rounded-2xl space-y-3">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#4a5320]" />
              <h2 className="text-xs font-bold font-mono uppercase text-[#4a5320] tracking-wider">
                What Retivue Is Not (Regulatory Boundary)
              </h2>
            </div>
            <p className="text-xs text-[#5a5d52] leading-relaxed font-mono">
              Retivue is strictly NOT an autonomous diagnostic device. It does not replace dilated slit-lamp biomicroscopy, optical coherence tomography (OCT), or a physician&apos;s medical judgement. All AI-generated lesion bounds and ICDR risk indicators are classified as decision support awaiting certified ophthalmologist adjudication.
            </p>
          </section>
        </div>

        <div className="mt-12 pt-6 border-t border-[#e8e4d8] flex items-center justify-between">
          <Link
            href="/"
            className="text-xs text-[#7a7d72] hover:text-[#1c1d1a] font-medium"
          >
            ← Back to Overview
          </Link>
          <Link
            href="/app"
            className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white text-xs font-semibold px-6 py-3 rounded-full transition-all shadow-sm hover:shadow no-underline"
          >
            <span>Open Clinical Portal</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </PublicLayout>
  );
}
