'use client';

import React from 'react';
import Link from 'next/link';
import { PublicLayout } from '@/layouts/PublicLayout';
import { ArrowRight, UploadCloud, ShieldCheck, Cpu, FileCheck2 } from 'lucide-react';

export default function HowItWorksPage() {
  const steps = [
    {
      num: '01',
      title: 'Acquisition',
      subtitle: 'Capture bilateral 45° fundus photography.',
      desc: 'Acquire 45° non-mydriatic fundus photographs (Right Eye OD and Left Eye OS) using standard clinic tabletop or handheld cameras.',
      details: [
        'Supports standard DICOM (.dcm), TIFF, PNG, and high-resolution JPEG',
        'Bilateral intake captures both macular and disc centers (Field 1 & Field 2)',
        'Local validation avoids unverified cloud transmissions',
      ],
      icon: UploadCloud,
    },
    {
      num: '02',
      title: 'Validation',
      subtitle: 'ISO 10940 pre-flight optical validation.',
      desc: 'Automated pre-flight checks evaluate focus sharpness (MTF), illumination uniformity, pupillary vignetting, and field centering before classification.',
      details: [
        'Instant detection of cataract haze, motion blur, and pupillary vignette',
        'Objective gradability grading: Gradable vs Ungradeable',
        'Prevents false reassurance by flagging retakes immediately',
      ],
      icon: ShieldCheck,
    },
    {
      num: '03',
      title: 'Analysis',
      subtitle: 'Microvascular pattern detection & ICDR staging.',
      desc: 'The neural backbone maps anatomical landmarks (optic disc, foveal avascular zone) and detects microaneurysms, blot hemorrhages, and lipid exudates.',
      details: [
        'Sub-pixel localization of early microvascular signs',
        'Quantitative lesion tallying across all 4 retinal quadrants',
        'Calibrated confidence intervals without black-box obfuscation',
      ],
      icon: Cpu,
    },
    {
      num: '04',
      title: 'Adjudication',
      subtitle: 'Ophthalmologist review workspace & clinical sign-off.',
      desc: 'The certified clinician reviews the fundus image with red-free filters, inspects AI evidence, accepts or overrides findings, and signs the encounter report.',
      details: [
        'Clear separation of AI decision support from physician assessment',
        'Structured ETDRS grading and referral window selection',
        'Direct generation of 21 CFR § 886.1100 compliant audit reports',
      ],
      icon: FileCheck2,
    },
  ];

  return (
    <PublicLayout>
      <div className="py-20 md:py-28 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 select-none">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
            CLINICAL TELE-SCREENING PIPELINE
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
            How Retivue Operates
          </h1>
          <p className="mt-4 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
            From community-level non-mydriatic fundus capture to specialist adjudication and tertiary hospital referral.
          </p>
        </div>

        <div className="space-y-6">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.num}
                className="p-6 sm:p-8 bg-white border border-[#e8e4d8] rounded-2xl flex flex-col md:flex-row items-start gap-6 shadow-xs"
              >
                <div className="w-12 h-12 rounded-full bg-[#f2f4e8] border border-[#d8debe] flex items-center justify-center shrink-0 text-[#4a5320] shadow-2xs">
                  <Icon size={22} />
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-[#7a7d72]">
                      STEP {step.num}
                    </span>
                    <span className="text-[#d8debe]">•</span>
                    <span className="text-xs font-mono text-[#4a5320] font-semibold uppercase">
                      {step.title}
                    </span>
                  </div>
                  <h3 className="font-serif text-lg text-[#1c1d1a]">
                    {step.subtitle}
                  </h3>
                  <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
                    {step.desc}
                  </p>
                  <ul className="pt-2 grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] font-mono text-[#5a5d52]">
                    {step.details.map((detail, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-[#4a5320] font-bold">✓</span>
                        <span>{detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-14 p-8 bg-[#f5f3ec] border border-[#e8e4d8] text-[#1c1d1a] rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-5 shadow-xs">
          <div>
            <h4 className="font-serif text-lg font-bold text-[#1c1d1a]">Ready to explore the clinical workspace?</h4>
            <p className="text-xs text-[#5a5d52] mt-1">
              Access the review workspace for independent doctors and screening clinics.
            </p>
          </div>
          <Link
            href="/app"
            className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-6 py-3 rounded-full text-xs font-semibold no-underline transition-all shadow-sm hover:shadow shrink-0"
          >
            <span>Launch Clinical Portal</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </PublicLayout>
  );
}
