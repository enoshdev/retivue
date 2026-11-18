'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { PublicLayout } from '@/layouts/PublicLayout';
import {
  ArrowRight,
  Cpu,
  Layers,
  Sparkles,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Eye,
  Scan,
  AlertTriangle,
  Database,
  UserCheck,
  Hospital,
  MapPin,
} from 'lucide-react';

export default function LandingPage() {
  // Interactive Product Preview Active Step (0 to 4)
  const [activeStep, setActiveStep] = useState<number>(0);

  // Interactive Explainability Layer Mode
  const [explainMode, setExplainMode] = useState<'ORIGINAL' | 'ATTENTION' | 'EVIDENCE'>('ATTENTION');

  const previewSteps = [
    {
      id: 'upload',
      num: '01',
      label: 'Upload',
      title: 'Retinal Image Acquisition',
      desc: 'Capture a 45° non-mydriatic fundus image. Supports JPG, PNG, and DICOM from desktop or handheld cameras.',
      status: 'ACQUISITION READY',
    },
    {
      id: 'quality',
      num: '02',
      label: 'Quality Check',
      title: 'Pre-Flight Optical Validation',
      desc: 'Automated ISO 10940 validation checks focus sharpness, illumination uniformity, and field centering before classification.',
      status: 'QUALITY VERIFIED',
    },
    {
      id: 'analysis',
      num: '03',
      label: 'Analysis',
      title: 'Microvascular Pattern Analysis',
      desc: 'Deep neural backbone maps optic disc, foveal avascular zone, and traces microaneurysms and hemorrhages.',
      status: 'PROCESSING EVIDENCE',
    },
    {
      id: 'result',
      num: '04',
      label: 'Screening Result',
      title: 'Clinical Triage Classification',
      desc: 'Standardized ICDR staging with ETDRS severity level and clear referral recommendations.',
      status: 'CLASSIFICATION COMPLETE',
    },
    {
      id: 'evidence',
      num: '05',
      label: 'Evidence',
      title: 'Explainable Attribution Layer',
      desc: 'Grad-CAM attention heatmap highlights anatomical regions that directly contributed to the screening decision.',
      status: 'EVIDENCE INSPECTED',
    },
  ];

  return (
    <PublicLayout>
      {/* ============================================================ */}
      {/* HERO SECTION                                                */}
      {/* ============================================================ */}
      <section className="relative pt-14 pb-20 md:pt-22 md:pb-32 overflow-hidden bg-[#faf9f5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center flex flex-col items-center">
          {/* Eyebrow Pill Badge (from Reference Image 1) */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#f2f4e8] border border-[#d8debe] text-[11px] font-mono tracking-widest text-[#4a5320] uppercase mb-8 shadow-2xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4a5320]" />
            AI-POWERED RETINAL SCREENING
          </div>

          {/* Master Headline (Playfair Display / Serif from Reference Image 1) */}
          <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-serif text-[#1c1d1a] tracking-tight leading-[1.08] max-w-4xl">
            See risk earlier.
          </h1>

          {/* Subtitle */}
          <p className="mt-7 text-base sm:text-lg md:text-xl text-[#4a4c44] max-w-2xl font-sans leading-relaxed">
            Retivue helps screen retinal images for signs associated with diabetic retinopathy and makes the visual evidence behind each screening result easier to understand.
          </p>

          {/* CTA Buttons (Pills from Reference Image 1) */}
          <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/app"
              className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-7 py-3.5 rounded-full text-sm font-semibold transition-all duration-200 shadow-sm hover:shadow no-underline"
            >
              <span>Start Screening</span>
              <ArrowRight size={15} />
            </Link>

            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-2 bg-white hover:bg-[#f5f3ec] text-[#1c1d1a] px-7 py-3.5 rounded-full text-sm font-semibold border border-[#e8e4d8] hover:border-[#ddd8c8] transition-all duration-200 no-underline shadow-2xs"
            >
              <span>How it works</span>
            </Link>
          </div>

          {/* ============================================================ */}
          {/* AUTHENTIC PRODUCT PREVIEW: REAL WORKFLOW SHOWCASE             */}
          {/* ============================================================ */}
          <div className="mt-14 md:mt-20 w-full max-w-5xl">
            {/* Step Selection Tabs */}
            <div className="flex items-center justify-center gap-2 pb-5 overflow-x-auto w-full">
              {previewSteps.map((step, idx) => (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => setActiveStep(idx)}
                  className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-mono transition-all duration-200 shrink-0 cursor-pointer ${
                    activeStep === idx
                      ? 'bg-[#4a5320] text-white font-bold shadow-xs'
                      : 'bg-white border border-[#e8e4d8] text-[#4a4c44] hover:text-[#1c1d1a] hover:border-[#ddd8c8]'
                  }`}
                >
                  <span className={activeStep === idx ? 'text-[#dee9a6]' : 'text-[#7a7d72]'}>
                    {step.num}
                  </span>
                  <span>{step.label}</span>
                </button>
              ))}
            </div>

            {/* Tablet Frame with Live Retivue Interface */}
            <div className="relative mx-auto rounded-2xl p-3 sm:p-5 bg-slate-950 shadow-2xl border border-slate-800">
              <div className="rounded-xl bg-[#020617] border border-slate-800 overflow-hidden text-left p-4 sm:p-6 text-white font-sans">
                {/* Console Header Bar */}
                <div className="flex flex-wrap items-center justify-between pb-4 mb-4 border-b border-slate-800 text-xs font-mono text-slate-400">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1.5 text-white font-semibold">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      RETIVUE CONSOLE
                    </span>
                    <span className="hidden sm:inline">•</span>
                    <span className="hidden sm:inline text-emerald-300">
                      {previewSteps[activeStep].title}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="px-2.5 py-1 rounded bg-slate-900 text-emerald-300 border border-slate-800">
                      STATUS: {previewSteps[activeStep].status}
                    </span>
                  </div>
                </div>

                {/* Main Viewport Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
                  {/* Left Column: Retinal Visual Container */}
                  <div className="lg:col-span-7 relative flex items-center justify-center bg-slate-950 rounded-xl p-4 border border-slate-800 overflow-hidden min-h-[340px]">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src="/retina-moderate-npdr.svg"
                      alt="Retinal Fundus Scan"
                      className="w-full max-h-[340px] object-contain rounded-lg"
                    />

                    {/* Step 02 Overlay: Quality Scan Grid */}
                    {activeStep === 1 && (
                      <div className="absolute inset-0 bg-[#020617]/50 backdrop-blur-[1px] flex flex-col justify-between p-5 pointer-events-none">
                        <div className="flex items-center justify-between text-[11px] font-mono text-emerald-400 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded w-fit">
                          <CheckCircle2 size={13} className="inline mr-1.5 text-emerald-400" />
                          ISO 10940 COMPLIANT • SUITABLE FOR SCREENING
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center text-[10px] font-mono">
                          <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-emerald-300">
                            FOCUS: OPTIMAL
                          </div>
                          <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-emerald-300">
                            ILLUMINATION: UNIFORM
                          </div>
                          <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-emerald-300">
                            FOV: 45° CENTERED
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Step 03 Overlay: Landmark Segmentation */}
                    {activeStep === 2 && (
                      <div className="absolute inset-0 pointer-events-none">
                        <svg viewBox="0 0 800 800" className="w-full h-full font-mono text-[11px]">
                          <ellipse
                            cx="270"
                            cy="400"
                            rx="50"
                            ry="60"
                            stroke="#34d399"
                            strokeWidth="2"
                            strokeDasharray="4 4"
                            fill="none"
                          />
                          <text x="270" y="325" fill="#34d399" textAnchor="middle" fontWeight="bold">
                            OPTIC DISC SEGMENTED
                          </text>

                          <circle
                            cx="490"
                            cy="415"
                            r="55"
                            stroke="#64748b"
                            strokeWidth="2"
                            strokeDasharray="3 3"
                            fill="none"
                          />
                          <circle cx="490" cy="415" r="4" fill="#ffffff" />
                          <text x="490" y="345" fill="#94a3b8" textAnchor="middle">
                            FOVEAL CENTER LOCATED
                          </text>
                        </svg>
                      </div>
                    )}

                    {/* Step 04 & 05 Overlay: Grad-CAM Attention Heatmap */}
                    {(activeStep === 3 || activeStep === 4) && (
                      <div className="absolute inset-0 pointer-events-none mix-blend-screen opacity-80">
                        <svg viewBox="0 0 800 800" className="w-full h-full">
                          <defs>
                            <radialGradient id="preview-grad" cx="62%" cy="48%" r="24%">
                              <stop offset="0%" stopColor="#ff0000" stopOpacity="0.85" />
                              <stop offset="35%" stopColor="#ff7700" stopOpacity="0.7" />
                              <stop offset="65%" stopColor="#ffff00" stopOpacity="0.45" />
                              <stop offset="100%" stopColor="#0044ff" stopOpacity="0" />
                            </radialGradient>
                          </defs>
                          <circle cx="496" cy="384" r="180" fill="url(#preview-grad)" />
                        </svg>
                      </div>
                    )}

                    <div className="absolute bottom-3 left-3 bg-[#020617]/90 border border-slate-800 px-2.5 py-1 rounded text-[10px] font-mono text-emerald-300">
                      LATERALITY: OD (RIGHT EYE) • 45° FOV
                    </div>
                  </div>

                  {/* Right Column: Workflow Context Card */}
                  <div className="lg:col-span-5 flex flex-col justify-between space-y-4">
                    <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>CURRENT STEP</span>
                        <span className="text-emerald-400 font-semibold">
                          STEP {previewSteps[activeStep].num} OF 05
                        </span>
                      </div>
                      <h4 className="text-xl font-semibold text-white">
                        {previewSteps[activeStep].title}
                      </h4>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {previewSteps[activeStep].desc}
                      </p>
                    </div>

                    {/* Stage Specific Telemetry Details */}
                    {activeStep === 0 && (
                      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                        <span className="text-[10px] font-mono uppercase text-slate-400 block">
                          ACQUISITION PARAMETERS
                        </span>
                        <div className="flex justify-between text-slate-300">
                          <span>Input Format:</span>
                          <span className="font-mono text-white">45° Fundus Photograph</span>
                        </div>
                        <div className="flex justify-between text-slate-300">
                          <span>Patient Privacy:</span>
                          <span className="font-mono text-emerald-400">Metadata Anonymized</span>
                        </div>
                      </div>
                    )}

                    {activeStep === 1 && (
                      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                        <span className="text-[10px] font-mono uppercase text-slate-400 block">
                          PRE-FLIGHT ASSESSMENT
                        </span>
                        <div className="flex justify-between text-slate-300">
                          <span>Overall Suitability:</span>
                          <span className="font-mono text-emerald-400 font-semibold">Suitable</span>
                        </div>
                        <div className="flex justify-between text-slate-300">
                          <span>Recapture Required:</span>
                          <span className="font-mono text-white">No</span>
                        </div>
                      </div>
                    )}

                    {activeStep === 2 && (
                      <div className="p-4 rounded-xl bg-[#0d0e11] border border-[#262a30] space-y-2 text-xs">
                        <span className="text-[10px] font-mono uppercase text-[#8e9298] block">
                          SEGMENTATION TELEMETRY
                        </span>
                        <div className="flex justify-between text-[#c4c7c8]">
                          <span>Optic Disc:</span>
                          <span className="font-mono text-white">Located (OD Margin)</span>
                        </div>
                        <div className="flex justify-between text-[#c4c7c8]">
                          <span>Macular Center:</span>
                          <span className="font-mono text-white">Located (FAZ Center)</span>
                        </div>
                      </div>
                    )}

                    {activeStep === 3 && (
                      <div className="p-4 rounded-xl bg-[#0d0e11] border border-[#262a30] space-y-2 text-xs">
                        <span className="text-[10px] font-mono uppercase text-[#8e9298] block">
                          CLASSIFICATION RESULT
                        </span>
                        <div className="flex justify-between text-slate-300">
                          <span>Triage Status:</span>
                          <span className="font-mono text-rose-400 font-semibold">Referable DR</span>
                        </div>
                        <div className="flex justify-between text-slate-300">
                          <span>Staging Grade:</span>
                          <span className="font-mono text-white">Moderate NPDR</span>
                        </div>
                      </div>
                    )}

                    {activeStep === 4 && (
                      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                        <span className="text-[10px] font-mono uppercase text-slate-400 block">
                          EXPLAINABILITY TRANSPARENCY
                        </span>
                        <div className="flex justify-between text-slate-300">
                          <span>Primary Attribution:</span>
                          <span className="font-mono text-white">Temporal Arcades</span>
                        </div>
                        <div className="flex justify-between text-slate-300">
                          <span>Evidence Method:</span>
                          <span className="font-mono text-emerald-400">Grad-CAM Attention Map</span>
                        </div>
                      </div>
                    )}

                    {/* Step Navigation Controls */}
                    <div className="flex items-center justify-between pt-1">
                      <button
                        type="button"
                        onClick={() => setActiveStep((s) => (s > 0 ? s - 1 : 4))}
                        className="text-xs text-slate-400 hover:text-white transition-colors cursor-pointer"
                      >
                        ← Previous step
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveStep((s) => (s < 4 ? s + 1 : 0))}
                        className="inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:text-white font-semibold transition-colors cursor-pointer"
                      >
                        <span>Next: {previewSteps[(activeStep + 1) % 5].label}</span>
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: THE SCREENING WORKFLOW (5 CLEAR STEPS)              */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#f5f3ec] border-y border-[#e8e4d8]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl">
            <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
              01 • WORKFLOW
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
              From capture to clinical review.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
              A transparent 5-step screening workflow designed for high-throughput primary health camps and tele-ophthalmology reading networks.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="p-6 bg-white rounded-2xl border border-[#e8e4d8] shadow-xs space-y-3">
              <span className="font-serif text-4xl text-[#4a5320] block font-normal">01</span>
              <h3 className="text-base font-semibold text-[#1c1d1a]">Upload</h3>
              <p className="text-xs text-[#5a5d52] leading-relaxed">
                45° non-mydriatic fundus photograph captured from clinic camera or portable ophthalmic kit.
              </p>
            </div>

            <div className="p-6 bg-white rounded-2xl border border-[#e8e4d8] shadow-xs space-y-3">
              <span className="font-serif text-4xl text-[#4a5320] block font-normal">02</span>
              <h3 className="text-base font-semibold text-[#1c1d1a]">Check</h3>
              <p className="text-xs text-[#5a5d52] leading-relaxed">
                Pre-flight optical evaluation verifies focus clarity, illumination balance, and centering.
              </p>
            </div>

            <div className="p-6 bg-white rounded-2xl border border-[#e8e4d8] shadow-xs space-y-3">
              <span className="font-serif text-4xl text-[#4a5320] block font-normal">03</span>
              <h3 className="text-base font-semibold text-[#1c1d1a]">Analyze</h3>
              <p className="text-xs text-[#5a5d52] leading-relaxed">
                Retinal landmark localization and microvascular biomarker extraction across all four quadrants.
              </p>
            </div>

            <div className="p-6 bg-white rounded-2xl border border-[#e8e4d8] shadow-xs space-y-3">
              <span className="font-serif text-4xl text-[#4a5320] block font-normal">04</span>
              <h3 className="text-base font-semibold text-[#1c1d1a]">Understand</h3>
              <p className="text-xs text-[#5a5d52] leading-relaxed">
                Inspect Grad-CAM heatmaps and visual evidence that explain the classification result.
              </p>
            </div>

            <div className="p-6 bg-white rounded-2xl border border-[#e8e4d8] shadow-xs space-y-3">
              <span className="font-serif text-4xl text-[#4a5320] block font-normal">05</span>
              <h3 className="text-base font-semibold text-[#1c1d1a]">Review</h3>
              <p className="text-xs text-[#5a5d52] leading-relaxed">
                Standardized report export supports clinician review and prioritized patient care coordination.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: IMAGE QUALITY TRIAGE                                */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#faf9f5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-center">
            <div className="lg:col-span-6 space-y-6">
              <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block font-semibold">
                02 • OPTICAL VALIDATION
              </span>
              <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
                Pre-flight quality validation before analysis begins.
              </h2>
              <p className="text-sm sm:text-base text-[#4a4c44] leading-relaxed">
                In community screening, up to 20% of captures can be degraded by cataract haze, motion blur, or flash reflection. Retivue checks image suitability immediately while the patient is still seated.
              </p>

              <div className="space-y-3 pt-2 text-xs sm:text-sm">
                <div className="p-4 rounded-xl bg-white border border-[#e8e4d8] flex items-start gap-3 shadow-2xs">
                  <div className="w-6 h-6 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center shrink-0 mt-0.5">
                    <CheckCircle2 size={14} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-[#1c1d1a]">Suitable</h4>
                    <p className="text-[#5a5d52] text-xs mt-0.5">
                      Vessel bifurcations and macular margin are sharp; proceeds directly to screening evaluation.
                    </p>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-white border border-[#e8e4d8] flex items-start gap-3 shadow-2xs">
                  <div className="w-6 h-6 rounded-full bg-amber-50 text-amber-700 flex items-center justify-center shrink-0 mt-0.5">
                    <AlertTriangle size={14} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-[#1c1d1a]">Needs Improvement</h4>
                    <p className="text-[#5a5d52] text-xs mt-0.5">
                      Minor illumination gradient or slight peripheral defocus; quality flags highlighted for review.
                    </p>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-white border border-[#e8e4d8] flex items-start gap-3 shadow-2xs">
                  <div className="w-6 h-6 rounded-full bg-rose-50 text-rose-700 flex items-center justify-center shrink-0 mt-0.5">
                    <XCircle size={14} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-[#1c1d1a]">Ungradeable</h4>
                    <p className="text-[#5a5d52] text-xs mt-0.5">
                      Diagnostic features obscured. Prevents false reassurance and prompts instant on-site recapture.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Quality Comparison Graphic */}
            <div className="lg:col-span-6 bg-white border border-[#e8e4d8] rounded-2xl p-6 sm:p-8 space-y-6 shadow-xs">
              <div className="flex items-center justify-between pb-3 border-b border-[#e8e4d8]">
                <span className="text-xs font-mono uppercase text-[#7a7d72] font-semibold">
                  ISO 10940 METRICS INSPECTION
                </span>
                <span className="text-xs font-mono text-[#4a5320] font-semibold flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#4a5320] animate-pulse" />
                  PRE-FLIGHT ACTIVE
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-[#0d0e11] border border-[#2a2d33] text-center space-y-2.5">
                  <div className="aspect-square relative flex items-center justify-center overflow-hidden rounded-lg bg-black">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src="/retina-normal.svg"
                      alt="Suitable Retinal Capture"
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <span className="text-xs font-mono text-emerald-400 block font-semibold">
                    SUITABLE CAPTURE
                  </span>
                  <span className="text-[11px] text-slate-400 block">
                    Sharp vascular bifurcations
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-[#0d0e11] border border-[#2a2d33] text-center space-y-2.5">
                  <div className="aspect-square relative flex items-center justify-center overflow-hidden rounded-lg bg-black opacity-80">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src="/retina-ungradeable.svg"
                      alt="Ungradeable Retinal Capture"
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <span className="text-xs font-mono text-rose-400 block font-semibold">
                    UNGRADEABLE CAPTURE
                  </span>
                  <span className="text-[11px] text-slate-400 block">
                    Recapture prompted immediately
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-[#f5f3ec] border border-[#e8e4d8] text-xs text-[#4a4c44]">
                <span className="font-semibold text-[#1c1d1a] block mb-1">
                  Why pre-flight verification matters:
                </span>
                Catching ungradeable captures on the spot prevents patient loss-to-follow-up, a leading failure point in community screening programs.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: RETINAL ANALYSIS & DR SEVERITY                      */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#f5f3ec] border-y border-[#e8e4d8]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mb-12">
            <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
              03 • CLINICAL PATHOLOGY
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
              Targeted analysis of retinal structures and lesions.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
              Instead of uninterpretable whole-image labels, Retivue evaluates hallmark diabetic retinopathy microvascular signs aligned with international ETDRS criteria.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white p-7 rounded-2xl border border-[#e8e4d8] space-y-4 shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center">
                <Eye size={20} />
              </div>
              <h3 className="text-lg font-semibold text-[#1c1d1a]">
                Anatomical Landmarks
              </h3>
              <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
                Localization of the optic disc and foveal center allows spatial triangulation of macular-threatening edema and arcade quadrants.
              </p>
            </div>

            <div className="bg-white p-7 rounded-2xl border border-[#e8e4d8] space-y-4 shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center">
                <Layers size={20} />
              </div>
              <h3 className="text-lg font-semibold text-[#1c1d1a]">
                Microvascular Lesions
              </h3>
              <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
                Identifies focal microaneurysms, intraretinal hemorrhages, and circinate lipid exudates associated with diabetic retinal breakdown.
              </p>
            </div>

            <div className="bg-white p-7 rounded-2xl border border-[#e8e4d8] space-y-4 shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center">
                <Cpu size={20} />
              </div>
              <h3 className="text-lg font-semibold text-[#1c1d1a]">
                Standardized ETDRS Staging
              </h3>
              <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
                Maps directly to ICDR stages: No DR, Mild NPDR, Moderate NPDR, Severe NPDR, and Proliferative DR with referral flags.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: EXPLAINABILITY — SEE THE EVIDENCE BEHIND THE RESULT */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#faf9f5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
              04 • TRANSPARENCY
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
              See the evidence behind the result.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-[#4a4c44] leading-relaxed">
              Retivue couples every screening evaluation with visual evidence, giving clinicians immediate insight into what the model observed.
            </p>

            {/* Mode Switcher */}
            <div className="mt-7 inline-flex p-1 rounded-full bg-[#edebe1] border border-[#e8e4d8] text-xs font-mono">
              <button
                type="button"
                onClick={() => setExplainMode('ORIGINAL')}
                className={`px-5 py-2 rounded-full transition-all duration-200 cursor-pointer ${
                  explainMode === 'ORIGINAL'
                    ? 'bg-[#4a5320] text-white font-semibold shadow-xs'
                    : 'text-[#4a4c44] hover:text-[#1c1d1a]'
                }`}
              >
                1. Original Scan
              </button>
              <button
                type="button"
                onClick={() => setExplainMode('ATTENTION')}
                className={`px-5 py-2 rounded-full transition-all duration-200 cursor-pointer ${
                  explainMode === 'ATTENTION'
                    ? 'bg-[#4a5320] text-white font-semibold shadow-xs'
                    : 'text-[#4a4c44] hover:text-[#1c1d1a]'
                }`}
              >
                2. Attention Heatmap
              </button>
              <button
                type="button"
                onClick={() => setExplainMode('EVIDENCE')}
                className={`px-5 py-2 rounded-full transition-all duration-200 cursor-pointer ${
                  explainMode === 'EVIDENCE'
                    ? 'bg-[#4a5320] text-white font-semibold shadow-xs'
                    : 'text-[#4a4c44] hover:text-[#1c1d1a]'
                }`}
              >
                3. Detected Evidence
              </button>
            </div>
          </div>

          {/* Interactive Explainability Viewport */}
          <div className="max-w-4xl mx-auto bg-white border border-[#e8e4d8] rounded-2xl p-6 sm:p-8 shadow-xs space-y-6">
            <div className="relative aspect-video max-h-[460px] w-full bg-[#0a0c0a] rounded-xl overflow-hidden border border-[#2a2d2a] flex items-center justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/retina-moderate-npdr.svg"
                alt="Retinal Explainability View"
                className="w-full h-full object-contain"
              />

              {/* Mode: Attention Grad-CAM */}
              {explainMode === 'ATTENTION' && (
                <div className="absolute inset-0 mix-blend-screen opacity-85 transition-opacity duration-300 pointer-events-none">
                  <svg viewBox="0 0 800 800" className="w-full h-full">
                    <defs>
                      <radialGradient id="exp-grad-1" cx="62%" cy="48%" r="22%">
                        <stop offset="0%" stopColor="#ff0000" stopOpacity="0.85" />
                        <stop offset="40%" stopColor="#ff9900" stopOpacity="0.65" />
                        <stop offset="70%" stopColor="#ffff00" stopOpacity="0.45" />
                        <stop offset="100%" stopColor="#0044ff" stopOpacity="0" />
                      </radialGradient>
                    </defs>
                    <circle cx="496" cy="384" r="176" fill="url(#exp-grad-1)" />
                  </svg>
                </div>
              )}

              {/* Mode: Evidence Reticles */}
              {explainMode === 'EVIDENCE' && (
                <div className="absolute inset-0 transition-opacity duration-300 pointer-events-none">
                  <svg viewBox="0 0 800 800" className="w-full h-full font-mono text-[11px]">
                    <g transform="translate(460, 340)">
                      <rect x="-16" y="-16" width="32" height="32" stroke="#f43f5e" strokeWidth="1.5" fill="none" />
                      <text x="22" y="4" fill="#f43f5e" fontWeight="bold">Microaneurysm Region</text>
                    </g>
                    <g transform="translate(520, 395)">
                      <circle cx="0" cy="0" r="26" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="3 3" fill="none" />
                      <text x="32" y="4" fill="#f59e0b" fontWeight="bold">Hard Exudates (Lipid)</text>
                    </g>
                  </svg>
                </div>
              )}

              <div className="absolute bottom-3 left-3 bg-[#0a0c0a]/90 border border-slate-700 px-3 py-1 rounded text-[10px] font-mono text-emerald-300">
                VIEW MODE: {explainMode}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[#f5f3ec] border border-[#e8e4d8] text-xs text-[#4a4c44] flex items-start gap-3">
              <Sparkles size={16} className="text-[#4a5320] shrink-0 mt-0.5" />
              <span>
                {explainMode === 'ORIGINAL'
                  ? 'Displays the raw, unaltered fundus photograph captured in the clinic.'
                  : explainMode === 'ATTENTION'
                  ? 'Highlighted regions show areas that contributed to the model’s prediction. Warmer colors indicate greater attribution weight.'
                  : 'Displays localized spatial reticles highlighting detected microvascular features across the diagnostic field.'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: HUMAN-IN-THE-LOOP & CLINICAL DECISION SUPPORT       */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#f5f3ec] border-y border-[#e8e4d8]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-6 space-y-6">
              <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block font-semibold">
                05 • HUMAN REVIEW
              </span>
              <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
                Designed for clinical decision support, not autonomous diagnosis.
              </h2>
              <p className="text-sm sm:text-base text-[#4a4c44] leading-relaxed">
                Retivue does not replace the ophthalmologist. It assists vision technicians and frontline healthcare staff in rural camps to prioritize referral queues so specialists can focus on actionable sight-threatening pathology.
              </p>

              <div className="space-y-3.5 pt-2">
                <div className="flex items-center gap-3 text-xs sm:text-sm text-[#1c1d1a]">
                  <CheckCircle2 size={18} className="text-[#4a5320] shrink-0" />
                  <span>AI-assisted screening triage — clear referral flags for high-risk cases</span>
                </div>
                <div className="flex items-center gap-3 text-xs sm:text-sm text-[#1c1d1a]">
                  <CheckCircle2 size={18} className="text-[#4a5320] shrink-0" />
                  <span>Visual evidence maps accelerate specialist review by up to 4x</span>
                </div>
                <div className="flex items-center gap-3 text-xs sm:text-sm text-[#1c1d1a]">
                  <CheckCircle2 size={18} className="text-[#4a5320] shrink-0" />
                  <span>Final diagnosis and treatment plans remain with qualified practitioners</span>
                </div>
              </div>
            </div>

            {/* Tri-stage Human-in-the-loop flow card */}
            <div className="lg:col-span-6 bg-white border border-[#e8e4d8] rounded-2xl p-6 sm:p-8 space-y-4 shadow-xs">
              <span className="text-xs font-mono uppercase text-[#7a7d72] font-semibold block">
                CLOSED-LOOP REVIEW PATHWAY
              </span>

              <div className="space-y-3 text-xs">
                <div className="p-4 rounded-xl bg-[#faf9f5] border border-[#e8e4d8] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#4a5320] text-white flex items-center justify-center font-mono font-bold text-xs">
                      1
                    </div>
                    <div>
                      <span className="font-bold text-[#1c1d1a] block text-sm">AI Screening Triage</span>
                      <span className="text-[#5a5d52] text-xs">Non-mydriatic fundus capture evaluated on edge device</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] px-2.5 py-0.5 rounded-full uppercase font-semibold">CAMP</span>
                </div>

                <div className="p-4 rounded-xl bg-[#faf9f5] border border-[#e8e4d8] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#4a5320] text-white flex items-center justify-center font-mono font-bold text-xs">
                      2
                    </div>
                    <div>
                      <span className="font-bold text-[#1c1d1a] block text-sm">Visual Evidence Layer</span>
                      <span className="text-[#5a5d52] text-xs">Grad-CAM attention map & lesion markers generated</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] px-2.5 py-0.5 rounded-full uppercase font-semibold">SYSTEM</span>
                </div>

                <div className="p-4 rounded-xl bg-[#faf9f5] border border-[#e8e4d8] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#4a5320] text-white flex items-center justify-center font-mono font-bold text-xs">
                      3
                    </div>
                    <div>
                      <span className="font-bold text-[#1c1d1a] block text-sm">Professional Review</span>
                      <span className="text-[#5a5d52] text-xs">Ophthalmologist reviews evidence & prescribes follow-up</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] px-2.5 py-0.5 rounded-full uppercase font-semibold">CLINICIAN</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: RESEARCH FOUNDATION & BENCHMARK DATASETS            */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#faf9f5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mb-12">
            <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
              06 • SCIENTIFIC FOUNDATION
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
              Built on retinal imaging research.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
              Retivue’s screening pipeline is developed and evaluated using established retinal imaging research datasets defined in SIH Problem Statement SIH26038.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* APTOS 2019 */}
            <div className="p-6 rounded-2xl bg-white border border-[#e8e4d8] space-y-4 shadow-xs flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] font-bold">
                    GRADING
                  </span>
                  <Database size={16} className="text-[#7a7d72]" />
                </div>
                <h3 className="text-lg font-semibold text-[#1c1d1a]">
                  APTOS 2019
                </h3>
                <p className="text-xs text-[#5a5d52] leading-relaxed">
                  Used for diabetic retinopathy severity classification across non-mydriatic fundus captures from rural screening camps.
                </p>
              </div>
              <div className="pt-3 border-t border-[#e8e4d8] text-[11px] font-mono text-[#7a7d72]">
                Focus: Clinical Severity Staging
              </div>
            </div>

            {/* IDRiD */}
            <div className="p-6 rounded-2xl bg-white border border-[#e8e4d8] space-y-4 shadow-xs flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] font-bold">
                    LESIONS
                  </span>
                  <Database size={16} className="text-[#7a7d72]" />
                </div>
                <h3 className="text-lg font-semibold text-[#1c1d1a]">
                  IDRiD
                </h3>
                <p className="text-xs text-[#5a5d52] leading-relaxed">
                  Indian Diabetic Retinopathy Image Dataset providing pixel-level lesion annotations for microaneurysms and exudates.
                </p>
              </div>
              <div className="pt-3 border-t border-[#e8e4d8] text-[11px] font-mono text-[#7a7d72]">
                Focus: Lesion Segmentation & Indian Cohorts
              </div>
            </div>

            {/* DRIVE */}
            <div className="p-6 rounded-2xl bg-white border border-[#e8e4d8] space-y-4 shadow-xs flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] font-bold">
                    VASCULAR
                  </span>
                  <Database size={16} className="text-[#7a7d72]" />
                </div>
                <h3 className="text-lg font-semibold text-[#1c1d1a]">
                  DRIVE
                </h3>
                <p className="text-xs text-[#5a5d52] leading-relaxed">
                  Digital Retinal Images for Vessel Extraction benchmark utilized for segmenting retinal vascular trees and caliber metrics.
                </p>
              </div>
              <div className="pt-3 border-t border-[#e8e4d8] text-[11px] font-mono text-[#7a7d72]">
                Focus: Retinal Vessel Tree Extraction
              </div>
            </div>

            {/* Messidor-2 */}
            <div className="p-6 rounded-2xl bg-white border border-[#e8e4d8] space-y-4 shadow-xs flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] font-bold">
                    EVALUATION
                  </span>
                  <Database size={16} className="text-[#7a7d72]" />
                </div>
                <h3 className="text-lg font-semibold text-[#1c1d1a]">
                  Messidor-2
                </h3>
                <p className="text-xs text-[#5a5d52] leading-relaxed">
                  Widely adopted clinical screening research benchmark for external evaluation of referable diabetic retinopathy models.
                </p>
              </div>
              <div className="pt-3 border-t border-[#e8e4d8] text-[11px] font-mono text-[#7a7d72]">
                Focus: External Evaluation & Triage
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: TELEMEDICINE & CARE COORDINATION                     */}
      {/* ============================================================ */}
      <section className="py-20 md:py-28 bg-[#f5f3ec] border-y border-[#e8e4d8]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
              07 • TELEMEDICINE
            </span>
            <h2 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
              Bridging the rural eye care divide.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-[#4a4c44] leading-relaxed">
              A coordinated care pathway linking primary screening centres to apex ophthalmic hospitals.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-[#e8e4d8] space-y-2 text-center shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center mx-auto mb-2">
                <MapPin size={18} />
              </div>
              <span className="text-[10px] font-mono text-[#7a7d72] block">STEP 01</span>
              <h4 className="font-semibold text-sm text-[#1c1d1a]">Screening Centre</h4>
              <p className="text-xs text-[#5a5d52]">Patient visits rural PHC or vision camp</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-[#e8e4d8] space-y-2 text-center shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center mx-auto mb-2">
                <Scan size={18} />
              </div>
              <span className="text-[10px] font-mono text-[#7a7d72] block">STEP 02</span>
              <h4 className="font-semibold text-sm text-[#1c1d1a]">Retinal Image</h4>
              <p className="text-xs text-[#5a5d52]">Non-mydriatic fundus photograph captured</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-[#e8e4d8] space-y-2 text-center shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center mx-auto mb-2">
                <Cpu size={18} />
              </div>
              <span className="text-[10px] font-mono text-[#7a7d72] block">STEP 03</span>
              <h4 className="font-semibold text-sm text-[#1c1d1a]">Retivue Triage</h4>
              <p className="text-xs text-[#5a5d52]">On-site quality check & risk evaluation</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-[#e8e4d8] space-y-2 text-center shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center mx-auto mb-2">
                <UserCheck size={18} />
              </div>
              <span className="text-[10px] font-mono text-[#7a7d72] block">STEP 04</span>
              <h4 className="font-semibold text-sm text-[#1c1d1a]">Clinical Review</h4>
              <p className="text-xs text-[#5a5d52]">Specialist examines evidence package</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-[#e8e4d8] space-y-2 text-center shadow-xs">
              <div className="w-10 h-10 rounded-full bg-[#f2f4e8] text-[#4a5320] flex items-center justify-center mx-auto mb-2">
                <Hospital size={18} />
              </div>
              <span className="text-[10px] font-mono text-[#7a7d72] block">STEP 05</span>
              <h4 className="font-semibold text-sm text-[#1c1d1a]">Care Follow-up</h4>
              <p className="text-xs text-[#5a5d52]">Laser therapy or annual community recall</p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* SECTION: FINAL CALL TO ACTION                                */}
      {/* ============================================================ */}
      <section className="py-24 md:py-32 bg-[#faf9f5] text-center">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
          <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] font-semibold block">
            GET STARTED
          </span>
          <h2 className="font-serif text-3xl sm:text-5xl md:text-6xl text-[#1c1d1a] leading-tight">
            Start screening with Retivue.
          </h2>
          <p className="text-base sm:text-lg text-[#4a4c44] max-w-xl mx-auto leading-relaxed">
            Experience explainable, AI-assisted retinal screening designed for community health and clinical decision support.
          </p>
          <div className="pt-4 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/app"
              className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-8 py-4 rounded-full text-sm font-semibold transition-all duration-200 shadow-sm hover:shadow no-underline"
            >
              <span>Launch Clinical Portal</span>
              <ArrowRight size={16} />
            </Link>

            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-2 bg-white hover:bg-[#f5f3ec] text-[#1c1d1a] px-8 py-4 rounded-full text-sm font-semibold border border-[#e8e4d8] hover:border-[#ddd8c8] transition-all duration-200 no-underline shadow-2xs"
            >
              <span>Explore how it works</span>
            </Link>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
